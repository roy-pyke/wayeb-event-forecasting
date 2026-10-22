#!/usr/bin/env python3
"""Run the authors' engine on reproducible, independent synthetic streams."""
import argparse
import csv
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from random import Random

from check_sources import ROOT, check


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate_stream(path, count, seed):
    """A small explicit second-order source; every symbol has positive probability."""
    rng = Random(seed)
    history = ["C", "A"]
    events = []
    for _ in range(count):
        if history[-2:] == ["A", "A"]:
            weights = (0.15, 0.70, 0.15)
        elif history[-1] == "A":
            weights = (0.25, 0.20, 0.55)
        elif history[-1] == "B":
            weights = (0.60, 0.25, 0.15)
        else:
            weights = (0.45, 0.20, 0.35)
        event = rng.choices(("A", "B", "C"), weights=weights, k=1)[0]
        events.append(event)
        history.append(event)
    with path.open("w", newline="") as out:
        csv.writer(out, lineterminator="\n").writerows((event, i + 1) for i, event in enumerate(events))
    return events


def oracle_matches(events):
    # Independent literal definition of the fixture A followed by (B or C).
    return [i + 1 for i in range(1, len(events)) if events[i - 1] == "A" and events[i] in ("B", "C")]


def run_cli(run_dir, name, *args):
    command = [str(ROOT / "wayeb"), *map(str, args)]
    log = run_dir / f"{name}.log"
    env = dict(os.environ, WAYEB_CONFIG_FILE=str(run_dir / "engine.conf"))
    with log.open("w") as out:
        result = subprocess.run(command, cwd=run_dir, env=env, stdout=out, stderr=subprocess.STDOUT, timeout=300)
    contents = log.read_text()
    if result.returncode or re.search(r"Exception in thread|\bERROR\b|Error:|OutOfMemoryError", contents):
        raise RuntimeError(f"{name} failed; inspect {log}\n" + contents[-4000:])
    print(f"Completed {name}", flush=True)
    return {"command": command, "returncode": result.returncode, "log": log.name}


def parse_forecast_stats(run_dir, name, kind):
    # The author regression writer appends .csv; the classification writer does not.
    candidates = list(run_dir.glob(f"{name}*"))
    expected_name = f"{name}_pattern.csv" if kind == "interval" else f"{name}_pattern"
    prediction = [p for p in candidates if p.is_file() and p.name == expected_name]
    if len(prediction) != 1:
        raise RuntimeError(f"Cannot identify forecast statistics for {name}: {[p.name for p in candidates]}")
    rows = list(csv.reader(prediction[0].open()))
    # Upstream writes headerless numeric rows.
    numbers = [float(x) for x in rows[-1]]
    if not all(math.isfinite(x) for x in numbers):
        raise AssertionError(f"Non-finite forecast metrics: {numbers}")
    if kind == "interval":
        keys = ("forecasts", "correct_forecasts", "precision", "detections", "missed", "loss_ratio", "mean_spread", "mean_distance", "mean_interval_score")
        metrics = dict(zip(keys, numbers))
        if metrics["forecasts"] <= 0 or not 0 <= metrics["precision"] <= 1:
            raise AssertionError(metrics)
    else:
        keys = ("precision", "recall", "f1", "specificity", "accuracy", "npv", "informedness", "mcc", "tp", "tn", "fp", "fn")
        metrics = dict(zip(keys, numbers))
        if sum(metrics[k] for k in ("tp", "tn", "fp", "fn")) <= 0:
            raise AssertionError(metrics)
    return {"file": prediction[0].name, "metrics": metrics}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    sources = check()
    if not (ROOT / "artifacts/wayeb.jar").exists():
        raise SystemExit("Run ./setup.sh first")
    config = json.loads((ROOT / "configs/demo.json").read_text())
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = (args.output or ROOT / "runs" / f"demo-{stamp}").resolve()
    run_dir.mkdir(parents=True, exist_ok=False)
    train_path, test_path = run_dir / "train.csv", run_dir / "test.csv"
    generate_stream(train_path, config["train_events"], config["train_seed"])
    test_events = generate_stream(test_path, config["test_events"], config["test_seed"])
    expected = oracle_matches(test_events)
    assert sha256(train_path) != sha256(test_path)
    (run_dir / "oracle_match_endpoints.json").write_text(json.dumps(expected) + "\n")
    (run_dir / "config.json").write_text(json.dumps(config, indent=2) + "\n")

    author_pattern = ROOT / "upstream/Wayeb/patterns/demo/a_seq_b_or_c.sre"
    patterns = run_dir / "pattern.sre"
    patterns.write_text(re.sub(r"\{order:\d+\}", "{order:" + str(config["order"]) + "}", author_pattern.read_text()))
    # Use HOCON because the author CLI incorrectly declares fractional PST options as Int.
    (run_dir / "engine.conf").write_text(
        'include classpath("application.conf")\n'
        'default.showMatchesForecasts = false\n'
        + "\n".join(f"vmm.{key} = {config[value]}" for key, value in (
            ("pMin", "pst_p_min"), ("alpha", "pst_alpha"), ("gammaMin", "pst_gamma_min"), ("r", "pst_r"))) + "\n"
    )
    declarations = ROOT / "upstream/Wayeb/patterns/demo/declarations.sre"
    fsm, mc, pst = run_dir / "pattern.fsm", run_dir / "pattern.mc", run_dir / "pattern.spst"
    steps = []
    steps.append(run_cli(run_dir, "compile", "compile", f"--patterns:{patterns}", f"--declarations:{declarations}", f"--outputFsm:{fsm}"))
    assert fsm.stat().st_size > 0
    steps.append(run_cli(run_dir, "recognition", "recognition", f"--fsm:{fsm}", f"--stream:{test_path}", f"--statsFile:{run_dir / 'recognition'}"))
    recognition_rows = list(csv.reader((run_dir / "recognition.csv").open()))
    actual_matches = int(recognition_rows[-1][2])
    assert actual_matches == len(expected), (actual_matches, len(expected))
    steps.append(run_cli(run_dir, "mle", "mle", f"--fsm:{fsm}", f"--stream:{train_path}", f"--outputMc:{mc}"))
    steps.append(run_cli(run_dir, "learnSPST", "learnSPST", "--fsmModel:dsfa", f"--patterns:{patterns}", f"--declarations:{declarations}", f"--stream:{train_path}", f"--outputSpst:{pst}"))
    assert mc.stat().st_size > 0 and pst.stat().st_size > 0

    forecasts = {}
    for model in ("fmm", "vmm"):
        model_args = [f"--modelType:{model}", f"--fsm:{fsm if model == 'fmm' else pst}"]
        if model == "fmm":
            model_args.append(f"--mc:{mc}")
        else:
            model_args.append("--fsmModel:dsfa")
        for method, kind in (("smart-scan", "interval"), ("classify-nextk", "classification")):
            name = f"{model}_{kind}"
            spread = config["interval_max_spread"] if kind == "interval" else config["classification_window"]
            steps.append(run_cli(run_dir, name, "forecasting", *model_args, f"--stream:{test_path}", f"--statsFile:{run_dir / name}", f"--foreMethod:{method}", f"--threshold:{config['confidence_threshold']}", f"--horizon:{config['horizon']}", f"--maxSpread:{spread}"))
            forecasts[name] = parse_forecast_stats(run_dir, name, kind)

    report = {
        "status": "passed", "scope": "synthetic deployment/integration validation; not reproduction of published real-data experiments",
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version, "platform": platform.platform(),
        "sources": sources["repositories"], "config": config,
        "inputs": {p.name: {"sha256": sha256(p), "events": config[key]} for p, key in ((train_path, "train_events"), (test_path, "test_events"))},
        "author_pattern_sha256": sha256(author_pattern), "run_pattern_sha256": sha256(patterns), "author_declarations_sha256": sha256(declarations),
        "oracle_matches": len(expected), "engine_matches": actual_matches,
        "forecasts": forecasts, "steps": steps,
        "artifacts": {p.name: sha256(p) for p in (fsm, mc, pst, ROOT / "artifacts/wayeb.jar")},
    }
    (run_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "output": str(run_dir), "matches": actual_matches, "forecasts": forecasts}, indent=2))


if __name__ == "__main__":
    main()

