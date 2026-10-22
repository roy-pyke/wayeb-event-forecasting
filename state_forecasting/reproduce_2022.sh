#!/usr/bin/env bash
set -euo pipefail
STATE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$STATE_ROOT"
STATE_OUTPUT="${1:-runs/state-confirmation-$(date -u +%Y%m%dT%H%M%SZ)}"
./state_forecasting/setup.sh
./state_forecasting/run.sh -m unittest discover -s state_forecasting/tests -v
./state_forecasting/run.sh state_forecasting/scripts/confirm_2022.py --output "$STATE_OUTPUT"
./state_forecasting/run.sh state_forecasting/scripts/verify_2022.py
./state_forecasting/run.sh state_forecasting/scripts/stress_fast.py --run "$STATE_OUTPUT"
./state_forecasting/run.sh state_forecasting/scripts/demo_fast.py --run "$STATE_OUTPUT"
./state_forecasting/run.sh state_forecasting/scripts/plot_confirmation.py
