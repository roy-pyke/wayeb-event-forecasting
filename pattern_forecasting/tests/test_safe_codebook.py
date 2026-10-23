import itertools
import numpy as np
import pytest
from patternforecast.automata import PatternFamily
from patternforecast.safe_codebook import (ForecastCodebook, Selector, encode_index,
    decode_index, offline_switches, replay)
from patternforecast.affine import loss_bound


def test_codebook_certificates_include_serialization_and_every_feasible_label():
    rng = np.random.default_rng(91)
    family = PatternFamily()
    book = ForecastCodebook(np.vstack([np.zeros(9), rng.random((7, 9))]), family, [1, 2, 3])
    states = np.repeat(np.arange(len(family.states)), 3)
    full = np.vstack([rng.dirichlet(np.ones(len(book.profiles[q])))@book.profiles[q] for q in states])
    bounds, distances = book.certificates(states, full)
    for i, q in enumerate(states):
        for j, candidate in enumerate(book.decoded[q]):
            expected = np.mean((candidate-book.profiles[q])**2-(full[i]-book.profiles[q])**2, axis=1).max()
            assert np.isclose(bounds[i, j], expected, atol=1e-12)
            assert np.isclose(distances[i, j], np.mean((candidate-full[i])**2), atol=1e-12)
            assert book.polytopes[q].contains(candidate)[0]
    assert book.setup_bytes == 8*9*4


def test_actual_index_frame_rejects_wrong_metadata_and_truncation():
    decoded = np.arange(27).reshape(3, 9)/30
    metadata = (123, 2, 9, 8, 0)
    packet = encode_index(metadata, 2, 3)
    assert len(packet) == 28
    index, p = decode_index(packet, metadata, decoded)
    assert index == 2 and np.array_equal(p, decoded[2])
    for i in range(5):
        wrong = list(metadata)
        wrong[i] += 1
        with pytest.raises(ValueError, match='metadata'):
            decode_index(packet, wrong, decoded)
    with pytest.raises(ValueError, match='length'):
        decode_index(packet[:-1], metadata, decoded)
    with pytest.raises(ValueError, match='encoding'):
        decode_index(packet[:-1]+b'\xff', metadata, decoded)
    with pytest.raises(ValueError):
        encode_index(metadata, 3, 3)


def test_offline_dynamic_program_matches_bruteforce():
    options = [np.array([(mask>>j)&1 for j in range(3)], dtype=bool) for mask in range(1, 8)]
    for requests in itertools.product(options, repeat=3):
        safe = np.array(requests)
        optimum = min(sum(a != b for a,b in zip((0,)+states[:-1], states))
            for states in itertools.product(range(3), repeat=3)
            if all(safe[i,j] for i,j in enumerate(states)))
        assert offline_switches(safe, np.zeros(3))['offline_codeword_switches'] == optimum
    # Covered runs separated by a common fallback require a fresh index.
    safe = np.array([[1,0], [0,0], [1,0], [1,0]], dtype=bool)
    assert offline_switches(safe, np.zeros(4)) == dict(offline_codeword_switches=1, covered_runs=2)
    assert offline_switches(safe, np.array([0,0,1,1]))['offline_codeword_switches'] == 0


def test_random_phase_exact_expected_moves_obey_harmonic_bound():
    # Enumerate every random branch on every length-four sequence over M=3.
    # The state carries (current ID, phase intersection, phase count, moves).
    options = [tuple(j for j in range(3) if mask>>j&1) for mask in range(1,8)]
    for requests in itertools.product(options, repeat=4):
        distribution = {(0, (), 0, 0): 1.0}
        for allowed in requests:
            nxt = {}
            for (current, old, phases, moves), probability in distribution.items():
                intersection = tuple(sorted(set(old)&set(allowed)))
                if not intersection:
                    intersection = allowed
                    phases += 1
                choices = (current,) if current in intersection else intersection
                for choice in choices:
                    key = (choice, intersection, phases, moves+int(choice!=current))
                    nxt[key] = nxt.get(key, 0)+probability/len(choices)
            distribution = nxt
        expected = sum(p*state[3] for state,p in distribution.items())
        phases = next(iter(distribution))[2]
        assert expected <= (1+1/2+1/3)*phases+1e-12
        safe = np.array([[j in allowed for j in range(3)] for allowed in requests])
        optimum = offline_switches(safe, np.zeros(4))['offline_codeword_switches']
        assert phases <= optimum+1


def test_replay_prefix_causality_and_same_fallback_for_all_policies():
    rng = np.random.default_rng(93)
    family = PatternFamily()
    book = ForecastCodebook(np.vstack([np.zeros(9), rng.random((7, 9))]), family, [1,2,3])
    n = 80
    states = rng.integers(len(family.states), size=n)
    full = np.vstack([rng.dirichlet(np.ones(len(book.profiles[q])))@book.profiles[q] for q in states])
    full[::4] = 0  # known covered requests interspersed with rare matches
    bounds, distances = book.certificates(states, full)
    data = dict(q=states, t=np.arange(n)+1000, entity=np.array(['station']*40+['house']*40),
                segment=np.repeat([0,1], 40))
    reference = None
    for policy in ['phase_uniform','uniform_current','nearest','minimum_certificate','recent_minimax_4','recent_minimax_16']:
        r = replay(data, full, book, bounds, distances, .002, policy, 101)
        assert (r['certificate'] <= .002+1e-9).all()
        assert np.all((r['bytes'][~r['fallback']] == 0)|(r['bytes'][~r['fallback']] == 28))
        if reference is None:
            reference = r
        else:
            mask = r['fallback']
            assert np.array_equal(r['bytes'][mask], reference['bytes'][mask])
            assert np.array_equal(r['pred'][mask], reference['pred'][mask])
        truncated = replay({k:v[:53] for k,v in data.items()}, full[:53], book, bounds[:53],
                           distances[:53], .002, policy, 101)
        assert np.array_equal(r['pred'][:53], truncated['pred'])
        assert np.array_equal(r['bytes'][:53], truncated['bytes'])
        for i, q in enumerate(states):
            assert np.isclose(r['certificate'][i], loss_bound(r['pred'][i].ravel(), full[i], book.profiles[q]))


def test_phase_intersection_really_tracks_past_safety():
    selector = Selector(3, 'phase_uniform', 0)
    selector.step(np.array([0,1,1],dtype=bool), np.array([1,0,0]), np.zeros(3))
    selector.step(np.array([1,1,0],dtype=bool), np.array([0,0,1]), np.zeros(3))
    assert selector.current == 1
    assert selector.phases == 1
    selector.step(np.array([1,0,1],dtype=bool), np.array([0,1,0]), np.zeros(3))
    assert selector.phases == 2
    assert selector.current in (0,2)
