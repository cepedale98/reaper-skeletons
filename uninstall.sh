#!/usr/bin/env bash
# Remove the current Skeletons install (scripts, JSFX, OSC, desktop launchers).
# User FXChains and reaper.ini HTTP/OSC rows are left in place.
# Keep this wrapper thin: the file list lives in skeletons/deploy.py so it
# changes with the app.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
cd "$ROOT"
exec python3 -m skeletons uninstall "$@"
