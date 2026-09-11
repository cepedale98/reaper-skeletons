#!/usr/bin/env python3
"""Build the empty role-tagged skeleton REAPER will fill with FX chains.

The GTK apps never instantiate plugins. Each tab is a track tagged
P_EXT:skel_role. REAPER loads .RfxChain files from
FXChains/<App>/<TAB>/*.RfxChain into those tracks (keeping tuner /
scope on IN). Live Control lives only on the SkeletonsGuitar folder track.

This builder writes:

  project/Skeletons.RPP                         full session (guitar + placeholders)
  project/SkeletonsGuitar.RTrackTemplate        guitar folder, Insert → TrackTemplates/SkeletonsGuitar

Usage: tools/build_skeleton.py
"""

from __future__ import annotations

import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_RPP = ROOT / "project" / "Skeletons.RPP"
OUT_APP_TPL = ROOT / "project" / "SkeletonsGuitar.RTrackTemplate"


def guid() -> str:
    return "{" + str(uuid.uuid4()).upper() + "}"


def jsfx_instance(ident: str, sliders: str) -> str:
    return (
        "    BYPASS 0 0 0\n"
        f'    <JS {ident} ""\n'
        f"      {sliders}\n"
        "    >\n"
        "    FLOATPOS 0 0 0 0\n"
        f"    FXID {guid()}\n"
        "    WAK 0 0\n"
    )


def pad_sliders(*values: str, total: int = 64) -> str:
    filled = list(values) + ["0"] * max(0, 16 - len(values))
    filled = filled[:16] + ["-"] * (total - 16)
    return " ".join(filled)


def bus_fxchain() -> str:
    """Skeletons Control on the SkeletonsGuitar folder track (live Param-link bank)."""
    return (
        "  <FXCHAIN\n"
        "    SHOW 0\n"
        "    LASTSEL 0\n"
        "    DOCKED 0\n"
        + jsfx_instance(
            "Skeletons/skel_control",
            pad_sliders("0.5", "0.5", "0.5", "0.35", "0.7", "0", "0", "0", "0", "1", "0", "0", "0", "0", "0", "0"),
        )
        + "  >\n"
    )


def input_fxchain() -> str:
    """Dry tuner/scope on IN. Hosted FX come from FXChains/SkeletonsGuitar/IN."""
    return (
        "  <FXCHAIN\n"
        "    SHOW 0\n"
        "    LASTSEL 0\n"
        "    DOCKED 0\n"
        + jsfx_instance("Skeletons/skel_tuner", pad_sliders("0", "-42"))
        + jsfx_instance("Skeletons/skel_scope", pad_sliders("0"))
        + "  >\n"
    )


def track(
    name: str,
    role: str,
    isbus: str,
    mainsend: str,
    *,
    rec: str = "0 -1 1 0 0 0 0 0",
    aux: list[tuple[int, float]] | None = None,
    fxchain: str | None = None,
    color: int = 16576,
) -> str:
    g = guid()
    chain = fxchain
    lines = [
        f"<TRACK {g}",
        f'  NAME "{name}"',
        f"  PEAKCOL {color}",
        "  BEAT -1",
        "  AUTOMODE 0",
        "  VOLPAN 1 0 -1 -1 1",
        "  MUTESOLO 0 0 0",
        "  IPHASE 0",
        "  PLAYOFFS 0 1",
        f"  ISBUS {isbus}",
        "  BUSCOMP 0 0 0 0 0",
        "  SHOWINMIX 1 0.6667 0.5 1 0.5 0 0 0 0",
        f"  REC {rec}",
        "  VU 64",
        "  TRACKHEIGHT 24 0 0 0 0 0 0",
        "  NCHAN 2",
        f"  FX {1 if chain else 0}",
        f"  TRACKID {g}",
        "  PERF 0",
        "  MIDIOUT -1",
    ]
    for src, vol in aux or ():
        lines.append(f"  AUXRECV {src} 0 {vol:.14g} 0 0 0 0 0 0 -1:U 0 -1 ''")
    lines.append(f"  MAINSEND {mainsend}")
    if chain:
        lines.append(chain.rstrip("\n"))
    lines.extend(
        [
            "  <EXT",
            f"    skel_role {role}",
            "  >",
            ">",
            "",
        ]
    )
    return "\n".join(lines)


def guitar_tracks() -> list[str]:
    # Indices: 0 bus, 1 input, 2 pedals, 3 amp, 4 cabinet, 5 fx
    pink = 22567838
    return [
        track("Skeletons Guitar", "guitar.bus", "1 1", "1 0", color=pink, fxchain=bus_fxchain()),
        track(
            "IN",
            "guitar.input",
            "0 0",
            "0 0",
            rec="1 1 1 0 0 0 0 0",
            fxchain=input_fxchain(),
            color=pink,
        ),
        track(
            "PEDALS",
            "guitar.pedals",
            "0 0",
            "0 0",
            aux=[(1, 1.0)],
            color=pink,
        ),
        track(
            "AMP",
            "guitar.amp",
            "0 0",
            "0 0",
            aux=[(2, 1.0)],
            color=pink,
        ),
        track(
            "CAB",
            "guitar.cabinet",
            "0 0",
            "1 0",
            aux=[(3, 1.0)],
            color=pink,
        ),
        track(
            "FX",
            "guitar.fx",
            "2 -1",
            "1 0",
            aux=[(3, 0.3981071705535)],
            color=pink,
        ),
    ]


def placeholder_tracks() -> list[str]:
    # Offset: guitar occupies 0-5. Names stay unique so untagged fallback works
    # in the mixed skeleton; FXChains folders are still SkeletonsKeyboard/IN etc.
    return [
        track("Skeletons Keyboard", "keys.bus", "1 1", "1 0"),
        track("Keys IN", "keys.input", "0 0", "1 0"),
        track("Keys INST", "keys.inst", "0 0", "1 0"),
        track("Keys FX", "keys.fx", "2 -1", "1 0"),
        track("Skeletons Microphone", "mic.bus", "1 1", "1 0"),
        track("Mic IN", "mic.input", "0 0", "1 0"),
        track("Mic FX", "mic.fx", "2 -1", "1 0"),
        track("Skeletons SideFX", "sidefx.bus", "1 1", "1 0"),
        track("REVERB", "sidefx.reverb", "0 0", "1 0"),
        track("DELAY", "sidefx.delay", "2 -1", "1 0"),
    ]


RPP_HEADER = """<REAPER_PROJECT 0.1 "7.79/linux-x86_64" 0 0
  RIPPLE 0 0
  GROUPOVERRIDE 0 0 0 0
  AUTOXFADE 129
  ENVATTACH 3
  MIXERUIFLAGS 11 52
  PEAKGAIN 1
  PANLAW 1
  CURSOR 0
  ZOOM 100 0 0
  VZOOMEX 24 0
  USE_REC_CFG 0
  RECMODE 1
  LOOP 0
  RECORD_PATH "" ""
  <RECORD_CFG
    ZXZhdxgAAQ==
  >
  RENDER_FMT 0 2 0
  TIMEMODE 1 5 -1 30 0 0 -1 0
  TEMPO 120 4 4
  PLAYRATE 1 0 0.25 4
  SELECTION 0 0
  SELECTION2 0 0
  MASTERAUTOMODE 0
  MASTERTRACKHEIGHT 0 0
  MASTERPEAKCOL 16576
  MASTERMUTESOLO 0
  MASTERTRACKVIEW 0 0.6667 0.5 0.5 0 0 0 0 0 0 0 0 0 0
  MASTERHWOUT 0 0 1 0 0 0 0 0
  MASTER_NCH 2 2
  MASTER_VOLUME 1 0 -1 -1 1
  MASTER_PANMODE 3
  MASTER_FX 0
  MASTER_SEL 0
"""


def main() -> int:
    guitar = guitar_tracks()
    others = placeholder_tracks()
    OUT_RPP.parent.mkdir(parents=True, exist_ok=True)
    OUT_RPP.write_text(RPP_HEADER + "".join(guitar + others) + ">\n", encoding="utf-8")
    body = "".join(guitar)
    OUT_APP_TPL.write_text(body, encoding="utf-8")
    print(f"wrote {OUT_RPP} ({len(guitar) + len(others)} tracks, empty of hosted FX)")
    print(f"wrote {OUT_APP_TPL} (guitar folder template)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
