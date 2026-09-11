#!/usr/bin/env bash
# Force the REAPER window onto KDE virtual Desktop 5.
set -euo pipefail

RULES="${XDG_CONFIG_HOME:-$HOME/.config}/kwinrulesrc"
DESKTOP5="e22b3432-0cde-4ee3-9d49-61ea182be037"

if [[ ! -f "$RULES" ]]; then
  echo "no $RULES — create a window rule for REAPER in System Settings first" >&2
  exit 1
fi

python3 - "$RULES" "$DESKTOP5" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
desktop = sys.argv[2]
text = path.read_text(encoding="utf-8")
parts, buf, current = [], [], None
for line in text.splitlines(keepends=True):
    if line.startswith("[") and line.strip().endswith("]"):
        if buf:
            parts.append((current, buf))
        current = line.strip()[1:-1]
        buf = [line]
    else:
        buf.append(line)
if buf:
    parts.append((current, buf))

found = False
out = []
for name, lines in parts:
    body = "".join(lines)
    if name and "wmclass=REAPER" in body:
        found = True
        rebuilt, seen_d, seen_r = [], False, False
        for line in lines:
            if line.startswith("desktops="):
                rebuilt.append(f"desktops={desktop}\n")
                seen_d = True
            elif line.startswith("desktopsrule="):
                rebuilt.append("desktopsrule=2\n")
                seen_r = True
            else:
                rebuilt.append(line)
        if not seen_d:
            rebuilt.append(f"desktops={desktop}\n")
        if not seen_r:
            rebuilt.append("desktopsrule=2\n")
        out.append("".join(rebuilt))
        print(f"updated rule {name} → Desktop 5 ({desktop})")
    else:
        out.append(body)

if not found:
    sys.exit("no kwin rule with wmclass=REAPER")
path.write_text("".join(out), encoding="utf-8")
PY

if command -v gdbus >/dev/null 2>&1; then
  gdbus call --session --dest org.kde.KWin --object-path /KWin --method org.kde.KWin.reconfigure >/dev/null \
    && echo "KWin reconfigured"
else
  echo "gdbus not found; log out or run: qdbus org.kde.KWin /KWin reconfigure"
fi
