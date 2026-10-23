"""Classical uniform-MSS policies applied to certified forecast codewords.

The randomized phase policy is prior art. This module tests its application,
including fixed codeword identity under public automaton-state decoding.
"""
import struct
import zlib
import numpy as np
from .wire import HEADER
from .affine import META, CoordinateMap, select_message, loss_bound
from .polytope import FeasiblePolytope

CODEWORD_FLAG = 128


def encode_index(metadata, index, size):
    if not 0 <= index < size <= 256:
        raise ValueError('invalid codeword index or codebook size')
    timestamp, entity, sequence, version, state = metadata
    return HEADER.pack(timestamp, entity, sequence, version) + META.pack(state, CODEWORD_FLAG) + bytes([index])


def decode_index(packet, metadata, decoded):
    if len(packet) != 28:
        raise ValueError('invalid index frame length')
    timestamp, entity, sequence, version = HEADER.unpack_from(packet)
    state, flag = META.unpack_from(packet, 24)
    if (timestamp, entity, sequence, version, state) != tuple(metadata):
        raise ValueError('index metadata mismatch')
    if flag != CODEWORD_FLAG or packet[-1] >= len(decoded):
        raise ValueError('invalid index encoding')
    return packet[-1], decoded[packet[-1]].copy()


class ForecastCodebook:
    def __init__(self, centers, family, horizons):
        # Serialize the shared codebook before either endpoint sees it.
        blob = np.asarray(centers, dtype='>f4').tobytes()
        self.centers = np.frombuffer(blob, dtype='>f4').astype(float).reshape(np.shape(centers))
        if not 1 <= len(self.centers) <= 256 or self.centers.shape[1] != 9:
            raise ValueError('codebook must have 1..256 nine-coordinate entries')
        if not np.isfinite(self.centers).all() or not np.array_equal(self.centers[0], np.zeros(9)):
            raise ValueError('finite centers and public zero initial codeword required')
        self.setup_bytes = len(blob)
        self.profiles = [family.feasible(q, tuple(horizons)).astype(float) for q in range(len(family.states))]
        self.polytopes = [FeasiblePolytope(y) for y in self.profiles]
        self.decoded = np.stack([p.project(self.centers) for p in self.polytopes])
        self.mapping = CoordinateMap.compile(np.vstack([np.zeros(9), np.eye(9)]), 'all')

    def project_full(self, states, full):
        result = np.asarray(full, dtype=float).reshape(-1, 9).copy()
        for q in np.unique(states):
            ix = states == q
            result[ix] = self.polytopes[int(q)].project(result[ix])
        return result

    def certificates(self, states, full):
        """Every codeword versus current f; no outcome labels are accessed."""
        full = np.asarray(full).reshape(-1, 9)
        bounds = np.empty((len(full), len(self.centers)))
        distances = np.empty_like(bounds)
        for q in np.unique(states):
            y = self.profiles[int(q)]
            g = self.decoded[int(q)]
            ids = np.flatnonzero(states == q)
            for offset in range(0, len(ids), 2048):
                ii = ids[offset:offset+2048]
                f = full[ii]
                bounds[ii] = ((g*g).sum(1)[None, :] - (f*f).sum(1)[:, None]
                    + 2*np.max((f@y.T)[:, None, :] - (g@y.T)[None, :, :], axis=2))/9
                distances[ii] = np.maximum(0, ((f*f).sum(1)[:, None] + (g*g).sum(1)[None, :] - 2*f@g.T)/9)
        return bounds, distances


class Selector:
    def __init__(self, size, policy, seed=20261022):
        if policy not in ('phase_uniform', 'nearest', 'minimum_certificate', 'uniform_current',
                          'recent_minimax_4', 'recent_minimax_16'):
            raise ValueError('unknown policy')
        self.size, self.policy = size, policy
        self.rng = np.random.default_rng(seed)
        self.reset()

    def reset(self):
        self.current = 0
        self.intersection = None
        self.recent = []
        self.phases = 0

    def step(self, safe, bounds, distances):
        self.recent.append(np.array(bounds, copy=True))
        self.recent = self.recent[-16:]
        if not np.any(safe):
            self.current = -1
            self.intersection = None
            return -1
        intersection = safe.copy() if self.intersection is None else self.intersection & safe
        if self.intersection is None or not intersection.any():
            intersection = safe.copy()
            self.phases += 1
        self.intersection = intersection
        allowed = intersection if self.policy == 'phase_uniform' else safe
        if self.current >= 0 and allowed[self.current]:
            return self.current
        ids = np.flatnonzero(allowed)
        if self.policy in ('phase_uniform', 'uniform_current'):
            self.current = int(self.rng.choice(ids))
        else:
            score = distances if self.policy == 'nearest' else bounds
            if self.policy.startswith('recent_minimax_'):
                window = int(self.policy.rsplit('_', 1)[1])
                score = np.max(self.recent[-window:], axis=0)
            self.current = int(ids[np.argmin(score[ids])])
        return self.current


def offline_switches(safe, segments):
    """Exact same-codebook lower bound; forced entries after uncovered queries.

    An offline state knows future safe sets. It is a diagnostic, not a causal
    performance baseline. Common fallback messages are counted elsewhere.
    """
    m = safe.shape[1]
    dp = np.full(m, np.inf)
    dp[0] = 0
    total = 0
    covered_runs = 0
    active = False
    for i, allowed in enumerate(safe):
        new_segment = i == 0 or segments[i] != segments[i-1]
        if new_segment:
            if active:
                total += int(dp.min())
            dp[:] = np.inf
            dp[0] = 0
            active = False
        if not allowed.any():
            if active:
                total += int(dp.min())
            dp[:] = 0  # mandatory ID on re-entry costs one, including codeword 0
            active = False
            continue
        if not active:
            covered_runs += 1
            if i > 0 and not new_segment and not safe[i-1].any():
                dp[:] = 1
        dp = np.minimum(dp, dp.min()+1)
        dp[~allowed] = np.inf
        active = True
    if active:
        total += int(dp.min())
    return dict(offline_codeword_switches=total, covered_runs=covered_runs)


def replay(data, full, codebook, bounds, distances, epsilon, policy, seed, version=1):
    n, m = bounds.shape
    full = np.asarray(full).reshape(-1, 9)
    pred = np.zeros_like(full)
    certificates = np.zeros(n)
    sizes = np.zeros(n, dtype=int)
    selected = np.full(n, -1, dtype=np.int16)
    fallback = np.zeros(n, dtype=bool)
    entities = {str(e): zlib.crc32(str(e).encode()) for e in np.unique(data['entity'])}
    if len(set(entities.values())) != len(entities):
        raise ValueError('entity registry collision')
    selector = Selector(m, policy, seed)
    receiver_index = 0
    previous_fallback = np.zeros(9)
    phase_total = 0
    for i in range(n):
        q = int(data['q'][i])
        poly = codebook.polytopes[q]
        if i == 0 or data['segment'][i] != data['segment'][i-1]:
            phase_total += selector.phases
            selector.reset()
            receiver_index = 0
            previous_fallback = np.zeros(9)
        safe = bounds[i] <= epsilon+1e-12
        index = selector.step(safe, bounds[i], distances[i])
        meta = (int(data['t'][i])*10**9, entities[str(data['entity'][i])], i, int(version), q)
        if index < 0:
            fallback[i] = True
            # Every policy enters this mode together. Its state is independent
            # of the preceding choice of codeword, for an equal fallback cost.
            cached = poly.project(previous_fallback) if receiver_index < 0 else np.zeros(9)
            if loss_bound(cached, full[i], codebook.profiles[q]) <= epsilon+1e-12:
                p = cached
                packet = b''
            else:
                p, _, packet, _ = select_message(np.zeros(9), full[i], codebook.profiles[q],
                    codebook.mapping, poly, epsilon, meta, partial=False)
            previous_fallback = p.copy()
            receiver_index = -1
        else:
            packet = b''
            if index != receiver_index:
                packet = encode_index(meta, index, m)
                receiver_index, p = decode_index(packet, meta, codebook.decoded[q])
            else:
                p = codebook.decoded[q, receiver_index].copy()
            selected[i] = receiver_index
        pred[i] = p
        certificates[i] = loss_bound(p, full[i], codebook.profiles[q])
        sizes[i] = len(packet)
        if certificates[i] > epsilon+1e-9:
            raise ArithmeticError('actual receiver forecast violates loss certificate')
    phase_total += selector.phases
    return dict(pred=pred.reshape(-1, 3, 3), full=full.reshape(-1, 3, 3), certificate=certificates,
        bytes=sizes, sends=sizes>0, selected=selected, fallback=fallback, phases=phase_total,
        codeword_packets=int(np.sum((sizes>0)&~fallback)), fallback_packets=int(np.sum((sizes>0)&fallback)),
        setup_bytes=codebook.setup_bytes*len(entities))
