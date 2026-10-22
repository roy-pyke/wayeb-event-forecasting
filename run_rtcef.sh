#!/usr/bin/env bash
source "$(dirname "$0")/scripts/common.sh"
cd "$WAYEB_PROJECT_ROOT"
export WAYEB_HOME="$WAYEB_PROJECT_ROOT/upstream/rtcef/libraries/models/wrappers/wayeb"
export PYTHONDONTWRITEBYTECODE=1
if [[ ! -x .venv-rtcef/bin/python || ! -f artifacts/rtcef-wayeb.jar ]]; then
  echo 'Run ./setup_rtcef.sh first.' >&2
  exit 1
fi
exec .venv-rtcef/bin/python scripts/run_rtcef.py "$@"

