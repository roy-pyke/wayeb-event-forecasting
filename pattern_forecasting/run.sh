#!/usr/bin/env bash
set -euo pipefail
PATTERN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$PATTERN_ROOT/pattern_forecasting/src${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=3 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg
exec "$PATTERN_ROOT/.venv-pattern/bin/python" "$@"
