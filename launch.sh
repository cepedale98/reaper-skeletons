#!/usr/bin/env bash
# Launch a Skeletons GTK 4 surface after verifying Gtk/Gdk 4.0 are pinned.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
cd "$ROOT"

module="${1:-apps.guitar}"

if ! python3 -m skeletons check; then
  echo
  echo "Fix the FAIL items above, then retry:  python3 -m skeletons install"
  exit 1
fi

echo
exec python3 -m "$module"
