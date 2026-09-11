#!/usr/bin/env bash
# Delete deprecated ReaperAPP / rapp_* copies that confuse REAPER after the
# Skeletons rebrand. Does not delete FXChains/GuitarApp (user rigs).
# Keep this wrapper thin: the file list lives in skeletons/deploy.py.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
cd "$ROOT"
exec python3 -m skeletons cleanup "$@"
