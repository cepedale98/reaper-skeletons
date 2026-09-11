#!/usr/bin/env python3
"""Audit (and optionally fix) PDC-critical Ratatouille controls in project files.

`buffered` changes the latency Ratatouille reports to the host. If two instances
disagree, or a preset varies it, REAPER recomputes delay compensation for the
whole graph and the resync is audible. The rule is that it holds one value
everywhere -- see docs/PDC.md.

This reads .RPP and .RTrackTemplate files directly so the rig can be normalised
before REAPER ever opens it. The live equivalent is ratatouille.audit() in the
agent, which reports drift at startup.

    tools/check_buffered.py                       # audit the repo and the template
    tools/check_buffered.py --fix path.RPP        # rewrite in place, keeping a .bak
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Must match rata.PINNED in reaper/skel_lib/ratatouille.lua.
PINNED = {"buffered": "1", "phase": "0"}

RATA_URI = "urn:brummer:ratatouille"
# A `P` line is a whitespace-separated run of name/value pairs; a plugin's
# parameters are split across several of them.
P_LINE = re.compile(r"^(\s*)P\s+(.*)$")


class Finding:
    def __init__(self, path: Path, track: str, lineno: int,
                 control: str, have: str, want: str):
        self.path, self.track, self.lineno = path, track, lineno
        self.control, self.have, self.want = control, have, want

    def __str__(self) -> str:
        return (f"{self.path.name}:{self.lineno}  track {self.track!r}  "
                f"{self.control} = {self.have}, expected {self.want}")


def current_track_name(lines: list[str], upto: int) -> str:
    """Nearest preceding NAME line, for a human-readable report."""
    for i in range(upto, -1, -1):
        stripped = lines[i].strip()
        if stripped.startswith("NAME "):
            return stripped[5:].strip().strip('"')
    return "?"


def scan(path: Path, fix: bool) -> tuple[list[Finding], bool]:
    text = path.read_text(encoding="utf-8", errors="replace")
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.replace("\r\n", "\n").split("\n")

    findings: list[Finding] = []
    changed = False
    in_rata = False
    depth = 0

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Only the first character may open or close a block; angle brackets
        # appear inside data elsewhere in the format.
        if stripped.startswith("<"):
            if RATA_URI in stripped:
                in_rata, depth = True, 1
            elif in_rata:
                depth += 1
            continue
        if stripped == ">":
            if in_rata:
                depth -= 1
                if depth == 0:
                    in_rata = False
            continue

        if not in_rata:
            continue

        match = P_LINE.match(line)
        if not match:
            continue

        indent, body = match.groups()
        tokens = body.split()
        touched = False
        for j in range(0, len(tokens) - 1, 2):
            name, value = tokens[j], tokens[j + 1]
            want = PINNED.get(name)
            if want is None or value == want:
                continue
            findings.append(
                Finding(path, current_track_name(lines, i), i + 1, name, value, want))
            if fix:
                tokens[j + 1] = want
                touched = True
        if touched:
            lines[i] = f"{indent}P " + " ".join(tokens)
            changed = True

    if fix and changed:
        backup = path.with_suffix(path.suffix + ".bak")
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_text(newline.join(lines), encoding="utf-8")

    return findings, changed


def default_targets() -> list[Path]:
    seen: dict[Path, None] = {}
    for pattern in ("*.RTrackTemplate", "*.RPP"):
        for p in sorted(ROOT.rglob(pattern)):
            if ".devenv" not in p.parts:
                seen[p] = None
    return list(seen)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", type=Path,
                        help="files to check (default: every project file in the repo)")
    parser.add_argument("--fix", action="store_true",
                        help="rewrite drifting values in place, keeping a .bak")
    args = parser.parse_args()

    targets = args.paths or default_targets()
    if not targets:
        print("no .RPP or .RTrackTemplate files found")
        return 0

    total: list[Finding] = []
    for path in targets:
        if not path.is_file():
            print(f"missing: {path}", file=sys.stderr)
            continue
        findings, changed = scan(path, args.fix)
        total.extend(findings)
        if findings:
            verb = "fixed" if changed else "drift"
            for f in findings:
                print(f"{verb}: {f}")
        else:
            print(f"ok: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")

    print()
    if not total:
        print("all pinned controls agree")
        return 0
    if args.fix:
        print(f"{len(total)} value(s) normalised; originals kept as .bak")
        return 0
    print(f"{len(total)} pinned control(s) drifting -- rerun with --fix")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
