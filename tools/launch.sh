#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
cd "$ROOT"
module="${1:-apps.guitar}"

if ! python3 -m skeletons check; then
  echo
  echo "Fix the FAIL items above, then retry:  python3 -m skeletons install"
  exit 1
fi

exec python3 -m "$module"
