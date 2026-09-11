#!/usr/bin/env bash
# Back-compat wrapper for python3 -m skeletons check
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
cd "$ROOT"
exec python3 -m skeletons check "$@"
