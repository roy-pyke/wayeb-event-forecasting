#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON_BIN="${RECURRENT_PYTHON:-.tools/acn/venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  python3.12 -m venv .tools/recurrent/venv
  PYTHON_BIN=.tools/recurrent/venv/bin/python
  "$PYTHON_BIN" -m pip install -r recurrent_research/requirements.txt
fi
"$PYTHON_BIN" recurrent_research/scripts/fetch.py
"$PYTHON_BIN" recurrent_research/scripts/prepare.py
"$PYTHON_BIN" -m pytest -q recurrent_research/tests
"$PYTHON_BIN" recurrent_research/scripts/run.py dev
"$PYTHON_BIN" recurrent_research/scripts/run.py test
"$PYTHON_BIN" recurrent_research/scripts/diagnose.py
"$PYTHON_BIN" recurrent_research/scripts/audit_baselines.py
"$PYTHON_BIN" recurrent_research/scripts/mechanism_audit.py
"$PYTHON_BIN" recurrent_research/scripts/independent.py
"$PYTHON_BIN" recurrent_research/scripts/plot.py
"$PYTHON_BIN" recurrent_research/scripts/verify.py
