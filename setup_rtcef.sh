#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
git submodule update --init --recursive
python3 scripts/check_sources.py
RTCEF_PYTHON="${WAYEB_PYTHON:-}"
if [[ -z "$RTCEF_PYTHON" ]]; then
  for candidate in python3.12 python3 /opt/anaconda3/bin/python3; do
    if "$candidate" -c 'import sys; assert sys.version_info[:2] == (3, 12)' 2>/dev/null; then
      RTCEF_PYTHON="$candidate"
      break
    fi
  done
fi
if [[ -z "$RTCEF_PYTHON" ]]; then
  echo 'CPython 3.12 is required. Set WAYEB_PYTHON to its executable.' >&2
  exit 1
fi
"$RTCEF_PYTHON" -c 'import sys; assert sys.version_info[:2] == (3, 12)'
if [[ ! -d .venv-rtcef ]]; then
  "$RTCEF_PYTHON" -m venv .venv-rtcef
fi
.venv-rtcef/bin/python -c 'import sys; assert sys.version_info[:2] == (3, 12), "Existing .venv-rtcef must use Python 3.12"'
.venv-rtcef/bin/python -m pip install --only-binary=:all: --no-binary=avro -r configs/requirements-rtcef.lock.txt
.venv-rtcef/bin/python -m pip check
./scripts/sbt.sh 'adaptive/assembly'
./scripts/install_kafka.sh

