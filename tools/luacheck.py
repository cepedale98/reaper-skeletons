#!/usr/bin/env python3
"""Syntax-check Skeletons Lua sources.

REAPER embeds Lua but offers no offline compiler, so this loads each file
through lupa's bundled interpreter and reports compile errors. It only checks
syntax: the reaper.* API is absent here, so nothing is executed.

Usage: tools/luacheck.py [paths...]   (defaults to reaper/**/*.lua)
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from lupa import LuaRuntime, LuaSyntaxError  # type: ignore
except ImportError:
    sys.exit("lupa not installed; run: .devenv/bin/pip install lupa")

ROOT = Path(__file__).resolve().parent.parent


def check(path: Path) -> str | None:
    source = path.read_text(encoding="utf-8")
    lua = LuaRuntime(unpack_returned_tuples=True)
    load = lua.eval("load")
    try:
        result = load(source, f"@{path.name}")
    except LuaSyntaxError as exc:
        return str(exc)
    # Lua's load() returns nil plus a message on a compile error rather than
    # raising, so the falsy case is the one that carries the diagnostic.
    if isinstance(result, tuple):
        chunk, message = (result + (None,))[:2]
        if chunk is None:
            return str(message)
    elif result is None:
        return "load() returned nil with no message"
    return None


def main(argv: list[str]) -> int:
    if argv:
        targets = [Path(a) for a in argv]
    else:
        targets = sorted((ROOT / "reaper").rglob("*.lua"))
        targets += sorted((ROOT / "tools").glob("*.lua"))

    failures = 0
    for path in targets:
        if not path.is_file():
            print(f"MISSING {path}")
            failures += 1
            continue
        error = check(path)
        rel = path.relative_to(ROOT) if path.is_absolute() else path
        if error:
            print(f"FAIL {rel}\n     {error}")
            failures += 1
        else:
            print(f"ok   {rel}")

    print(f"\n{len(targets) - failures}/{len(targets)} files compile")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
