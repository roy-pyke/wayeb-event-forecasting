#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ $# -gt 1 || ( $# -eq 1 && "$1" != "--core" ) ]]; then
  echo 'Usage: ./reproduce.sh [--core]' >&2
  exit 1
fi
./setup.sh
./scripts/sbt.sh 'core/testOnly Specs.model.waitingTime.WaitingTimeSpec Specs.vmm.PST Specs.srem.NSRAeqSREM'
./run_demo.sh
if [[ "${1:-}" != "--core" ]]; then
  ./setup_rtcef.sh
  ./run_rtcef.sh
fi

