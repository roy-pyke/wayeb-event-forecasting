"""Development experiment: intentionally never loads the sealed holdout split."""
import argparse
import json
import platform
import subprocess
import time
from pathlib import Path
import joblib
import numpy as np
from .data import PACKAGE, ROOT, load_split, prepare, sha256, targets
from .model import StateSurvival
from .evaluate import metrics, paired_bootstrap


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--iterations", type=int, default=180)
    parser.add_argument("--leaves", type=int, default=15)
    parser.add_argument("--min-leaf", type=int, default=40)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    protocol = json.loads((PACKAGE / "configs/PROTOCOL.json").read_text())
    prepared = prepare(protocol)
    train, select, calibration, development = [load_split(prepared, s) for s in
                                               ("train", "select", "calibrate", "development")]
    train_ids = set(train["instance"])
    assert all(not train_ids.intersection(d["instance"]) for d in [select, calibration, development])
    horizons = protocol["horizons_seconds"]
    report = dict(scope="development only; holdout unopened", config=vars(args) | {"output": str(args.output)},
                  protocol_sha256=sha256(PACKAGE / "configs/PROTOCOL.json"),
                  git_head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                  source_hashes={str(p.relative_to(PACKAGE)): sha256(p) for p in sorted((PACKAGE / "src").rglob("*.py"))},
                  data_manifest=json.loads((prepared / "manifest.json").read_text()), platform=platform.platform(),
                  candidates={}, models={})
    models = {}
    for mode, bins in [("M0", 0), ("M1", 4), ("M1", 8), ("M1", 16), ("M2", 0)]:
        name = mode if mode != "M1" else f"M1-{bins}"
        before = time.perf_counter()
        model = StateSurvival(mode, protocol["hazard_edges_seconds"], bins=bins,
                              max_iter=args.iterations, max_leaf_nodes=args.leaves,
                              min_samples_leaf=args.min_leaf).fit(train)
        validation = metrics(select, model.predict_cdf(select["X"], horizons), horizons)
        report["candidates"][name] = {"selection": validation, "fit_seconds": time.perf_counter()-before,
                                       "hazard_training_rows": model.fit_rows}
        models[name] = model
        print(f"{name}: selection mean Brier={validation['mean_brier']:.6f} fit {report['candidates'][name]['fit_seconds']:.2f}s", flush=True)
    best_discrete = min([k for k in models if k.startswith("M1")], key=lambda k: report["candidates"][k]["selection"]["mean_brier"])
    report["selected_discrete"] = best_discrete
    predictions = {}
    for name in ["M0", best_discrete, "M2"]:
        model = models[name]
        raw = model.predict_cdf(development["X"], horizons)
        model.calibrate(calibration, horizons)
        prediction = model.predict_cdf(development["X"], horizons)
        predictions[name] = prediction
        joblib.dump(model, args.output / f"{name}.joblib")
        summary = {"raw": metrics(development, raw, horizons),
                   "calibrated": metrics(development, prediction, horizons),
                   "model_sha256": sha256(args.output / f"{name}.joblib")}
        report["models"][name] = summary
        print(f"{name}: development raw={summary['raw']['mean_brier']:.6f} calibrated={summary['calibrated']['mean_brier']:.6f} ECE60={summary['calibrated']['60']['ece']:.5f}", flush=True)
    report["comparisons"] = {
        name: paired_bootstrap(development, predictions["M0"], predictions[name], horizons)
        for name in [best_discrete, "M2"]}
    report["continuous_vs_discrete"] = paired_bootstrap(development, predictions[best_discrete], predictions["M2"], horizons)
    best_context = min([best_discrete, "M2"], key=lambda n: report["models"][n]["calibrated"]["mean_brier"])
    report["selected_context"] = best_context
    report["relative_reduction"] = 1 - report["models"][best_context]["calibrated"]["mean_brier"] / report["models"]["M0"]["calibrated"]["mean_brier"]
    np.savez_compressed(args.output / "development_predictions.npz", **predictions)
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ["selected_context", "relative_reduction", "comparisons", "continuous_vs_discrete"]}, indent=2))


if __name__ == "__main__":
    main()
