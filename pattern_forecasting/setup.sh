#!/usr/bin/env bash
set -euo pipefail
PATTERN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PATTERN_ROOT"
PATTERN_PYTHON="${WAYEB_PYTHON:-/opt/anaconda3/bin/python3}"
"$PATTERN_PYTHON" -c 'import sys; assert sys.version_info[:2] == (3, 12)'
[[ -d .venv-pattern ]] || "$PATTERN_PYTHON" -m venv .venv-pattern
.venv-pattern/bin/python -m pip install --only-binary=:all: -r pattern_forecasting/configs/requirements.txt
.venv-pattern/bin/python -m pip check
mkdir -p runs/pattern-bridge
./wayeb compile --patterns:pattern_forecasting/configs/patterns.sre --declarations:pattern_forecasting/configs/declarations.sre --outputFsm:runs/pattern-bridge/patterns.fsm
./scripts/sbt.sh 'patternBridge/run runs/pattern-bridge/patterns.fsm runs/pattern-bridge/dfa.json ordered,branch_loop,overlap_loop'
.venv-pattern/bin/python - <<'PY'
from pathlib import Path
import json
source=Path('runs/pattern-bridge/dfa.json')
target=Path('pattern_forecasting/configs/dfa.json')
if target.exists():
    assert json.loads(target.read_text()) == json.loads(source.read_text())
else:
    target.write_text(source.read_text())
PY
