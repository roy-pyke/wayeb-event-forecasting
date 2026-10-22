"""Causal features and episode-level temporal splits for the public MetroPT data."""
from collections import deque
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile
import numpy as np
import pandas as pd
from .stream import ContextState, Event

PACKAGE = Path(__file__).resolve().parents[2]
ROOT = PACKAGE.parent
CACHE = ROOT / ".cache/state_forecasting"
URL = "https://archive.ics.uci.edu/static/public/791/metropt%2B3%2Bdataset.zip"
ZIP_SHA = "aab991a970e58210de853bb8078ce0e63abb4d9412fdc5c79792dae3d8e1721a"
SENSORS = ["TP2", "TP3", "H1", "DV_pressure", "Reservoirs", "Oil_temperature", "Motor_current"]
BASE = ["age_seconds", "previous_duration", "previous_three_mean", "hour_sin", "hour_cos"]
CONTEXT = SENSORS + [s + "_rate" for s in SENSORS]
FEATURES = BASE + CONTEXT + ["report_age"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def download():
    CACHE.mkdir(parents=True, exist_ok=True)
    archive = CACHE / "metropt3.zip"
    if not archive.exists():
        temp = archive.with_suffix(".tmp")
        urllib.request.urlretrieve(URL, temp)
        if sha256(temp) != ZIP_SHA:
            raise ValueError("download checksum mismatch")
        temp.rename(archive)
    if sha256(archive) != ZIP_SHA:
        raise ValueError("MetroPT archive checksum mismatch")
    return archive


def read_raw():
    with zipfile.ZipFile(download()) as archive:
        with archive.open("MetroPT3(AirCompressor).csv") as stream:
            frame = pd.read_csv(stream, usecols=["timestamp", "COMP", *SENSORS])
    times = pd.to_datetime(frame.timestamp).astype("int64").to_numpy() / 1e9
    if np.any(np.diff(times) <= 0):
        raise ValueError("timestamps must strictly increase")
    return times, frame.COMP.to_numpy(), frame[SENSORS].to_numpy()


def episodes(times, comp, gap_seconds):
    """No future value is used to decide a start; terminal index is a label only."""
    active = None
    for i in range(1, len(times)):
        if times[i] - times[i - 1] > gap_seconds or not np.isfinite(comp[i]):
            if active is not None:
                yield active, i - 1, False
            active = None
            continue
        if active is None and comp[i - 1] == 1 and comp[i] == 0:
            active = i
        elif active is not None and comp[i] == 1:
            yield active, i, True
            active = None
    if active is not None:
        yield active, len(times) - 1, False


def episode_rows(times, sensors, start, stop, observed, history, spacing,
                 delay=0.0, drop_probability=0.0, rng=None):
    """Feature extraction replayed from available prefixes only.

    stop and observed are used for offline labels and stopping, never features.
    Query schedule depends only on elapsed past time, never episode length.
    """
    context = ContextState(len(SENSORS))
    pending = deque()
    last_query = -float("inf")
    rows = []
    end_index = stop if observed else stop + 1
    for i in range(start, end_index):
        now = times[i]
        if drop_probability == 0 or rng.random() >= drop_probability:
            pending.append(Event("apu", "Telemetry", now, now + delay, tuple(sensors[i])))
        while pending and pending[0].arrival_time <= now:
            context.accept(pending.popleft())
        if now - last_query < spacing:
            continue
        last_query = now
        z, fresh = context.snapshot(now)
        phase = 2 * np.pi * (now % 86400) / 86400
        base = [now - times[start], history[-1] if history else np.nan,
                np.mean(history) if history else np.nan, np.sin(phase), np.cos(phase)]
        rows.append((now, times[stop] - now, observed, np.r_[base, z, fresh]))
    return rows


def prepare(protocol, force=False, delay=0.0, drop_probability=0.0):
    suffix = "" if delay == drop_probability == 0 else f"-delay{delay:g}-drop{drop_probability:g}"
    destination = CACHE / ("prepared" + suffix)
    if (destination / "manifest.json").exists() and not force:
        old = json.loads((destination / "manifest.json").read_text())
        if old["protocol_sha256"] == sha256(PACKAGE / "configs/PROTOCOL.json") and old["data_source_sha256"] == sha256(__file__):
            return destination
    destination.mkdir(parents=True, exist_ok=True)
    times, comp, sensors = read_raw()
    boundaries = {k: tuple(pd.Timestamp(s).timestamp() for s in limits)
                  for k, limits in protocol["splits"].items()}
    records = {k: [] for k in boundaries}
    history = deque(maxlen=3)
    business = []
    omitted = 0
    rng = np.random.default_rng(protocol["seed"])
    count = 0
    for eid, (start, stop, observed) in enumerate(episodes(times, comp, protocol["gap_censor_seconds"])):
        count += 1
        business.extend([("LoadStart", times[start], eid),
                         ("LoadEnd" if observed else "Gap", times[stop], eid)])
        split = next((key for key, (a, b) in boundaries.items()
                      if a <= times[start] and times[stop] < b), None)
        if split is None:
            omitted += 1
        else:
            for now, residual, obs, x in episode_rows(
                    times, sensors, start, stop, observed, history,
                    protocol["landmark_min_spacing_seconds"], delay, drop_probability, rng):
                records[split].append((eid, now, residual, obs, times[start], x))
        if observed:
            history.append(times[stop] - times[start])
    summary = {}
    for split, rows in records.items():
        if not rows:
            raise ValueError(f"empty split {split}")
        eid, now, residual, observed, start, features = zip(*rows)
        arrays = dict(instance=np.asarray(eid), time=np.asarray(now), residual=np.asarray(residual),
                      observed=np.asarray(observed), start=np.asarray(start), X=np.asarray(features))
        path = destination / f"{split}.npz"
        np.savez_compressed(path, **arrays)
        summary[split] = {"rows": len(rows), "instances": len(set(eid)), "sha256": sha256(path),
                          "censored_instances": len(set(np.asarray(eid)[~np.asarray(observed)]))}
    with (destination / "business.csv").open("w") as f:
        for kind, timestamp, _ in business:
            f.write(f"{kind},{int(timestamp)}\n")
    manifest = dict(archive_sha256=ZIP_SHA, source_url=URL, doi="10.24432/C5VW3R", licence="CC BY 4.0",
                    rows_raw=len(times), actual_median_interval_seconds=float(np.median(np.diff(times))),
                    gap_count=int(np.sum(np.diff(times) > protocol["gap_censor_seconds"])),
                    instances=count, boundary_crossing_instances_omitted=omitted,
                    features=FEATURES, splits=summary, delay=delay, drop_probability=drop_probability,
                    protocol_sha256=sha256(PACKAGE / "configs/PROTOCOL.json"), data_source_sha256=sha256(__file__))
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return destination


def load_split(directory, name):
    with np.load(Path(directory) / f"{name}.npz") as archive:
        return {k: archive[k] for k in archive.files}


def instance_weights(data):
    _, inverse, counts = np.unique(data["instance"], return_inverse=True, return_counts=True)
    return 1.0 / counts[inverse]


def targets(data, horizons):
    r = data["residual"][:, None]
    h = np.asarray(horizons)[None, :]
    y = (data["observed"][:, None] & (r <= h)).astype(int)
    known = data["observed"][:, None] | (r >= h)
    return y, known
