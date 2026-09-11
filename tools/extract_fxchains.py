#!/usr/bin/env python3
"""Carve .RfxChain files out of the Cleantonic template into fxchains/guitar/cleantonic/."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "Cleantonic AME MIX.RTrackTemplate"
OUT = ROOT / "fxchains" / "guitar" / "cleantonic"


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def parse_tracks(text: str) -> list[str]:
    lines = normalize(text).split("\n")
    tracks: list[str] = []
    cur: list[str] | None = None
    depth = 0
    for line in lines:
        trimmed = line.strip()
        first = trimmed[:1]
        if depth == 0:
            if trimmed.startswith("<TRACK"):
                cur, depth = [line], 1
        else:
            assert cur is not None
            cur.append(line)
            if first == "<":
                depth += 1
            elif trimmed == ">":
                depth -= 1
                if depth == 0:
                    tracks.append("\n".join(cur) + "\n")
                    cur = None
    return tracks


def extract_fxchain(chunk: str) -> str | None:
    lines = chunk.split("\n")
    start = None
    depth = 0
    for i, line in enumerate(lines):
        trimmed = line.strip()
        if start is None:
            if trimmed.startswith("<FXCHAIN"):
                start, depth = i, 1
        else:
            if trimmed.startswith("<"):
                depth += 1
            elif trimmed == ">":
                depth -= 1
                if depth == 0:
                    return "\n".join(lines[start : i + 1]) + "\n"
    return None


TAGS = {"VST", "LV2", "JS", "CLAP", "AU", "DX", "CONTAINER"}
TRAILING = ("WET", "FLOATPOS", "FXID", "WAK", "JS_DIMS", "PRESET", "COMMENT")


def fx_instances(fxchain: str) -> list[str]:
    """Each FX plus the BYPASS before it and WET/FXID/WAK after it."""
    lines = fxchain.split("\n")
    spans: list[tuple[int, int]] = []
    i = 1  # skip <FXCHAIN
    while i < len(lines):
        trimmed = lines[i].strip()
        if trimmed.startswith("<") and trimmed[1:].split()[0:1] and trimmed[1:].split()[0] in TAGS:
            start = i
            if i > 0 and lines[i - 1].strip().startswith("BYPASS"):
                start = i - 1
            depth = 0
            j = i
            while j < len(lines):
                t = lines[j].strip()
                if t.startswith("<"):
                    depth += 1
                elif t == ">":
                    depth -= 1
                    if depth == 0:
                        j += 1
                        while j < len(lines):
                            head = lines[j].strip().split(" ", 1)[0]
                            if head in TRAILING:
                                j += 1
                                continue
                            break
                        spans.append((start, j))
                        i = j
                        break
                j += 1
            else:
                break
            continue
        i += 1
    return ["\n".join(lines[a:b]) + "\n" for a, b in spans]


def fx_name(block: str) -> str:
    for line in block.split("\n"):
        trimmed = line.strip()
        if trimmed.startswith("<"):
            tag = trimmed[1:].split()[0] if trimmed[1:] else ""
            if tag in TAGS:
                m = re.search(r'"([^"]+)"', trimmed)
                return (m.group(1) if m else trimmed).lower()
    return block[:80].lower()


def wrap(instances: list[str]) -> str:
    return "<FXCHAIN\nSHOW 0\nLASTSEL 0\nDOCKED 0\n" + "".join(instances) + ">\n"


def write(name: str, instances: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(wrap(instances), encoding="utf-8")
    print(f"  {path.relative_to(ROOT)}  ({len(instances)} FX)")


def main() -> int:
    tracks = parse_tracks(TEMPLATE.read_text(encoding="utf-8", errors="replace"))
    if len(tracks) < 4:
        raise SystemExit("template does not have 4 tracks")
    _bus, inp, amp, verb = tracks[:4]
    inp_fx = fx_instances(extract_fxchain(inp) or "")
    amp_fx = fx_instances(extract_fxchain(amp) or "")
    verb_fx = fx_instances(extract_fxchain(verb) or "")

    input_keep, pedals = [], []
    for inst in inp_fx:
        n = fx_name(inst)
        if "distortion" in n or "1175" in n:
            pedals.append(inst)
        else:
            input_keep.append(inst)

    amp_keep, cab = [], []
    for inst in amp_fx:
        n = fx_name(inst)
        if "chorus" in n:
            cab.append(inst)
        else:
            amp_keep.append(inst)

    print("extracting FX chains from", TEMPLATE.name)
    write("input.RfxChain", input_keep)
    write("pedals.RfxChain", pedals)
    write("amp.RfxChain", amp_keep)
    write("cabinet.RfxChain", cab)
    write("fx.RfxChain", verb_fx)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
