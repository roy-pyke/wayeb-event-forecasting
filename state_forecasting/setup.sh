#!/usr/bin/env bash
set -euo pipefail
STATE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$STATE_ROOT"
STATE_PYTHON="${WAYEB_PYTHON:-python3.12}"
if ! command -v "$STATE_PYTHON" >/dev/null 2>&1; then
  if [[ -x /opt/anaconda3/bin/python3 ]]; then STATE_PYTHON=/opt/anaconda3/bin/python3; else STATE_PYTHON=python3; fi
fi
"$STATE_PYTHON" -c 'import sys; assert sys.version_info[:2] == (3,12), "CPython 3.12 required"'
if [[ ! -d .venv-state ]]; then "$STATE_PYTHON" -m venv .venv-state; fi
.venv-state/bin/python -m pip install --only-binary=:all: -r state_forecasting/configs/requirements.lock.txt
.venv-state/bin/python -m pip check
[[ -f artifacts/wayeb.jar ]] || ./setup.sh
mkdir -p runs/state-bridge
./wayeb compile --patterns:state_forecasting/configs/pattern.sre --declarations:state_forecasting/configs/declarations.sre --outputFsm:runs/state-bridge/pattern.fsm
./scripts/sbt.sh 'stateBridge/run runs/state-bridge/pattern.fsm runs/state-bridge/dfa.json'
# Compare semantic transitions, ignoring JSON key formatting/order.
.venv-state/bin/python - <<'PY'
import json
from pathlib import Path
assert json.loads(Path('runs/state-bridge/dfa.json').read_text()) == json.loads(Path('state_forecasting/configs/dfa.json').read_text())
PY
