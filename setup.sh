#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
git submodule update --init --recursive
python3 scripts/check_sources.py
./scripts/sbt.sh 'core/assembly'

