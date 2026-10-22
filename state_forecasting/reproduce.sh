#!/usr/bin/env bash
set -euo pipefail
STATE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$STATE_ROOT"
STATE_OUTPUT="${1:-runs/state-reproduction-$(date -u +%Y%m%dT%H%M%SZ)}"
./state_forecasting/setup.sh
./state_forecasting/run.sh -m unittest discover -s state_forecasting/tests -v
./state_forecasting/run.sh -c 'import json; from stateforecast.data import prepare,PACKAGE; prepare(json.loads((PACKAGE/"configs/PROTOCOL.json").read_text()))'
./state_forecasting/run.sh state_forecasting/scripts/verify_wayeb.py
./state_forecasting/run.sh state_forecasting/scripts/controls.py
./state_forecasting/run.sh state_forecasting/scripts/final_holdout.py --output "$STATE_OUTPUT"
./state_forecasting/run.sh state_forecasting/scripts/stress.py --run "$STATE_OUTPUT"
./state_forecasting/run.sh state_forecasting/scripts/demo.py --run "$STATE_OUTPUT"
