#!/usr/bin/env bash
set -euo pipefail
PATTERN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PATTERN_ROOT"
PATTERN_PYTHON="${WAYEB_PYTHON:-/opt/anaconda3/bin/python3}"
"$PATTERN_PYTHON" -c 'import sys; assert sys.version_info[:2] == (3, 12)'
[[ -d .venv-pattern ]] || "$PATTERN_PYTHON" -m venv .venv-pattern
.venv-pattern/bin/python -m pip install --only-binary=:all: -r pattern_forecasting/configs/requirements.txt
.venv-pattern/bin/python -m pip check
PATTERN_VARIANT="${PATTERN_FAMILY:-nested}"
PATTERN_CONFIG="pattern_forecasting/configs"
PATTERN_NAMES="ordered,branch_loop,overlap_loop"
PATTERN_POLICY="nonoverlap"
if [[ "$PATTERN_VARIANT" == directional ]]; then
  PATTERN_CONFIG="pattern_forecasting/configs/directional"
  PATTERN_NAMES="rising,falling,excursion"
  PATTERN_POLICY="overlap"
fi
if [[ "$PATTERN_VARIANT" == multisignal ]]; then
  PATTERN_CONFIG="pattern_forecasting/configs/multisignal"
  PATTERN_NAMES="response_up,response_down,response_any"
  PATTERN_POLICY="overlap"
fi
export PATTERN_CONFIG
mkdir -p "runs/pattern-bridge-$PATTERN_VARIANT"
./wayeb compile --patterns:"$PATTERN_CONFIG/patterns.sre" --declarations:"$PATTERN_CONFIG/declarations.sre" --countPolicy:"$PATTERN_POLICY" --outputFsm:"runs/pattern-bridge-$PATTERN_VARIANT/patterns.fsm"
./scripts/sbt.sh "patternBridge/run runs/pattern-bridge-$PATTERN_VARIANT/patterns.fsm runs/pattern-bridge-$PATTERN_VARIANT/dfa.json $PATTERN_NAMES"
.venv-pattern/bin/python - <<'PY'
from pathlib import Path
import json
import os
source=Path('runs')/('pattern-bridge-'+os.environ.get('PATTERN_FAMILY','nested'))/'dfa.json'
target=Path(os.environ['PATTERN_CONFIG'])/'dfa.json'
if target.exists():
    assert json.loads(target.read_text()) == json.loads(source.read_text())
else:
    target.write_text(source.read_text())
PY
