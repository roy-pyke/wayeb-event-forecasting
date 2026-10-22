"""Causal prequential adaptation; labels become available only after observation."""
import argparse
import json
from pathlib import Path
import time
import joblib
import numpy as np
import pandas as pd
from .data import PACKAGE, ROOT, CACHE, load_split, sha256
from .model import StateSurvival
from .evaluate import metrics, paired_bootstrap, subset


def concatenate(parts):
    return {k: np.concatenate([part[k] for part in parts]) for k in parts[0]}


def asof(data, cutoff, start_after, started_before=None):
    """Censor every unknown terminal label at the current wall clock.

    Retain still-running instances; dropping them would bias duration learning.
    Inference cannot see the offline terminal time through residual/observed.
    """
    mask = (data["time"] < cutoff) & (data["start"] >= start_after)
    if started_before is not None:
        mask &= data["start"] < started_before
    result = subset(data, mask)
    elapsed_followup = cutoff - result["time"]
    result["observed"] = result["observed"] & (result["residual"] <= elapsed_followup)
    result["residual"] = np.minimum(result["residual"], elapsed_followup)
    assert np.all(result["time"] + result["residual"] <= cutoff + 1e-7)
    return result


def replay(pool, evaluation, protocol, out, window_days=14, calibration_days=2,
           iterations=180, leaves=15, calibration_enabled=True):
    out.mkdir(parents=True, exist_ok=False)
    horizons = protocol["horizons_seconds"]
    predictions = {name: np.zeros((len(evaluation["time"]), len(horizons))) for name in ["M0", "M1-16", "M2"]}
    raw_predictions = {name: np.zeros_like(p) for name, p in predictions.items()}
    audits = []
    days = np.unique(evaluation["time"] // 86400)
    for day in days:
        now = day * 86400
        cut = now - calibration_days * 86400
        train = asof(pool, cut, now - window_days*86400, started_before=cut)
        calibration = asof(pool, now, cut)
        target = (evaluation["time"] >= now) & (evaluation["time"] < now+86400)
        train_ids = set(train["instance"])
        assert not train_ids.intersection(calibration["instance"])
        # Train and calibration labels are clipped above; query rows start now.
        assert (not len(calibration["time"]) or calibration["time"].max() < now)
        assert now <= evaluation["time"][target].min()
        audit = dict(update_time=float(now), date=str(pd.Timestamp(now, unit="s").date()),
                     train_queries=len(train["time"]), calibration_queries=len(calibration["time"]),
                     train_latest_information=float(np.max(train["time"]+train["residual"])),
                     calibration_latest_information=float(np.max(calibration["time"]+calibration["residual"])) if len(calibration["time"]) else None,
                     calibration_policy="identity_if_empty_otherwise_shared_isotonic",
                     first_query=float(evaluation["time"][target].min()), models={})
        start_time = time.perf_counter()
        for mode, name in [("M0", "M0"), ("M1", "M1-16"), ("M2", "M2")]:
            model = StateSurvival(mode, protocol["hazard_edges_seconds"], bins=16,
                                  max_iter=iterations, max_leaf_nodes=leaves).fit(train)
            raw_predictions[name][target] = model.predict_cdf(evaluation["X"][target], horizons)
            if calibration_enabled:
                model.calibrate(calibration, horizons)
            predictions[name][target] = model.predict_cdf(evaluation["X"][target], horizons)
            model_path = out / f"{audit['date']}-{name}.joblib"
            joblib.dump(model, model_path)
            audit["models"][name] = {"sha256": sha256(model_path), "bytes": model_path.stat().st_size}
        audit["fit_seconds"] = time.perf_counter() - start_time
        audits.append(audit)
        print(f"{audit['date']} train={audit['train_queries']} calibration={audit['calibration_queries']} queries={target.sum()} fit={audit['fit_seconds']:.2f}s", flush=True)
    report = dict(strategy="daily rolling landmark survival", window_days=window_days,
                  calibration_days=calibration_days, calibration_enabled=calibration_enabled,
                  iterations=iterations, leaves=leaves, updates=audits,
                  source_hashes={str(p.relative_to(PACKAGE)): sha256(p) for p in sorted((PACKAGE / "src").rglob("*.py"))},
                  protocol_sha256=sha256(PACKAGE / "configs/PROTOCOL.json"), models={})
    for name in predictions:
        report["models"][name] = dict(calibrated=metrics(evaluation, predictions[name], horizons),
                                    raw=metrics(evaluation, raw_predictions[name], horizons))
    report["comparisons"] = {name: paired_bootstrap(evaluation, predictions["M0"], predictions[name], horizons)
                             for name in ["M1-16", "M2"]}
    report["continuous_vs_discrete"] = paired_bootstrap(evaluation, predictions["M1-16"], predictions["M2"], horizons)
    report["relative_reduction"] = 1-report["models"]["M2"]["calibrated"]["mean_brier"]/report["models"]["M0"]["calibrated"]["mean_brier"]
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    np.savez_compressed(out / "predictions.npz", **predictions)
    np.savez_compressed(out / "raw_predictions.npz", **raw_predictions)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--window-days", type=int, default=14)
    parser.add_argument("--calibration-days", type=int, default=2)
    parser.add_argument("--iterations", type=int, default=180)
    parser.add_argument("--leaves", type=int, default=15)
    args = parser.parse_args()
    protocol = json.loads((PACKAGE / "configs/PROTOCOL.json").read_text())
    parts = [load_split(CACHE / "prepared", s) for s in ["train", "select", "calibrate", "development"]]
    report = replay(concatenate(parts), parts[-1], protocol, args.output,
                    args.window_days, args.calibration_days, args.iterations, args.leaves)
    print(json.dumps({k: report[k] for k in ["relative_reduction", "comparisons", "continuous_vs_discrete"]}, indent=2))


if __name__ == "__main__":
    main()
