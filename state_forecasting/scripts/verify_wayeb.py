"""Differential endpoint test against the actual authors' recognition engine."""
import csv
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import numpy as np
from stateforecast.data import ROOT, PACKAGE, CACHE, sha256
from stateforecast.stream import Event, WayebMonitor


def main():
    out = ROOT / "runs/state-recognition"
    out.mkdir(parents=True, exist_ok=True)
    fsm = ROOT / "runs/state-bridge/pattern.fsm"
    table = json.loads((PACKAGE / "configs/dfa.json").read_text())
    conf = out / "engine.conf"
    conf.write_text('include classpath("application.conf")\ndefault.showMatchesForecasts = true\n')
    datasets = {"metropt": CACHE / "prepared/business.csv"}
    rng = np.random.default_rng(20261022)
    random_path = out / "random.csv"
    with random_path.open("w") as stream:
        for i, kind in enumerate(rng.choice(table["alphabet"], 10000)):
            stream.write(f"{kind},{i+1}\n")
    datasets["random"] = random_path
    report = {"scope": "actual Wayeb CLI differential endpoint validation", "datasets": {},
              "table_sha256": sha256(PACKAGE / "configs/dfa.json"),
              "author_jar_sha256": sha256(ROOT / "artifacts/wayeb.jar")}
    for name, path in datasets.items():
        monitor, enriched = WayebMonitor(table), WayebMonitor(table)
        expected = []
        previous = None
        with path.open() as stream:
            for kind, stamp in csv.reader(stream):
                stamp = int(stamp)
                if previous == "LoadStart" and kind == "LoadEnd":
                    expected.append(stamp)
                previous = kind
                event = Event("apu", kind, stamp, stamp)
                monitor.accept(event)
                enriched.accept(Event("apu", "Telemetry", stamp, stamp, (0.8,)))
                enriched.accept(event)
        assert expected == [t for _, t in monitor.matches]
        assert monitor.matches == enriched.matches
        log = out / f"{name}.log"
        with log.open("w") as stream:
            result = subprocess.run([str(ROOT / "wayeb"), "recognition", f"--fsm:{fsm}",
                                     f"--stream:{path}", f"--statsFile:{out / name}"],
                                    cwd=out, env=dict(os.environ, WAYEB_CONFIG_FILE=str(conf)),
                                    stdout=stream, stderr=subprocess.STDOUT, timeout=180)
        text = log.read_text()
        if result.returncode or "Exception" in text or "ERROR" in text:
            raise RuntimeError(text[-2000:])
        observed = list(map(int, re.findall(r"MATCH:\s+Timestamp->(\d+)", text)))
        assert observed == expected, (name, len(observed), len(expected))
        report["datasets"][name] = dict(matches=len(expected), endpoint_mismatches=0, input_sha256=sha256(path))
    report["status"] = "passed"
    (PACKAGE / "reports/recognition.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
