#!/usr/bin/env python3
"""Exercise the pure-Lua libraries against real project data.

chunk.lua and json.lua contain the fiddliest logic in the project and neither
touches the reaper.* API, so both can be driven directly from a host Lua
interpreter. This asserts against the actual Cleantonic template rather than a
fixture, so the format details it relies on stay honest.

Usage: tools/selftest_lua.py
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from lupa import LuaRuntime  # type: ignore
except ImportError:
    sys.exit("lupa not installed; run: .devenv/bin/pip install lupa")

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "Cleantonic AME MIX.RTrackTemplate"
RATA_URI = "urn:brummer:ratatouille"

failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"ok   {label}")
    else:
        print(f"FAIL {label}" + (f"\n     {detail}" if detail else ""))
        failures.append(label)


def make_runtime() -> "LuaRuntime":
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(f'package.path = "{ROOT / "reaper"}/?.lua;" .. package.path')
    return lua


def require(lua: "LuaRuntime", name: str):
    """require() also returns the loader path, which tuple unpacking exposes."""
    module = lua.eval(f'require("{name}")')
    return module[0] if isinstance(module, tuple) else module


def test_json() -> None:
    lua = make_runtime()
    json = require(lua, "skel_lib.json")

    encoded = json.encode(lua.table_from({"b": 2, "a": "x\ty"}))
    check("json: keys sorted and tab escaped",
          encoded == '{"a":"x\\ty","b":2}', encoded)

    roundtrip = json.decode('{"n":1.5,"t":true,"s":"\\u00e9","a":[1,2,3]}')
    check("json: decode scalars", roundtrip["n"] == 1.5 and roundtrip["t"] is True)
    check("json: decode \\u escape", roundtrip["s"] == "é", repr(roundtrip["s"]))
    check("json: decode array", list(roundtrip["a"].values()) == [1, 2, 3])

    check("json: empty table is an object", json.encode(lua.table()) == "{}")
    check("json: forced array", json.encode(json.array(lua.table())) == "[]")

    # A malformed file must return nil plus a message, never raise, because the
    # agent decodes preset files from inside a defer loop.
    ok, err = json.decode_file(str(ROOT / "does-not-exist.json"))
    check("json: missing file returns error", ok is None and err is not None, repr(err))


def test_chunk() -> None:
    lua = make_runtime()
    chunk = require(lua, "skel_lib.chunk")

    text = TEMPLATE.read_text(encoding="utf-8")
    doc = chunk.load(text)

    tracks = chunk.track_nodes(doc)
    names = []
    for i in range(1, len(tracks) + 1):
        names.append(chunk.get_field(tracks[i], "NAME"))
    check("chunk: four top-level TRACK blocks", len(tracks) == 4, str(len(tracks)))
    check("chunk: track names parsed",
          names == ['"GUITAR RACK"', "INPUT", '"AMP / CAB"', "REVERB"], str(names))

    # Byte-fidelity matters: we edit one line of a chunk containing large base64
    # VST payloads and hand the rest straight back to REAPER.
    check("chunk: serialize round-trips unedited input",
          chunk.serialize(doc) == text.replace("\r\n", "\n"))

    # INPUT is track 2 and carries the first Ratatouille.
    input_fx = chunk.fx_nodes(tracks[2])
    fx_names = [chunk.fx_display_name(input_fx[i]) for i in range(1, len(input_fx) + 1)]
    check("chunk: INPUT has 5 FX", len(input_fx) == 5, str(fx_names))
    check("chunk: mid-line angle brackets did not break parsing",
          any("ReaFir" in n for n in fx_names), str(fx_names))
    check("chunk: Ratatouille found on INPUT",
          any("Ratatouille" in n for n in fx_names), str(fx_names))

    rata_index = next(
        (i for i in range(1, len(input_fx) + 1)
         if "Ratatouille" in chunk.fx_display_name(input_fx[i])),
        None,
    )
    check("chunk: Ratatouille locatable", rata_index is not None)
    if rata_index is None:
        return

    rata = input_fx[rata_index]
    state = chunk.get_state(rata)
    model = state[f"{RATA_URI}#Neural_Model"]
    check("chunk: reads the NAM path from <STATE>",
          isinstance(model, str) and model.endswith(".nam"), repr(model))
    check("chunk: empty slot reads as None",
          state[f"{RATA_URI}#Neural_Model1"] == "None",
          repr(state[f"{RATA_URI}#Neural_Model1"]))

    # The arming path rewrites exactly one <STATE> line and nothing else.
    before = chunk.serialize(doc).splitlines()
    changed = chunk.set_state(doc, rata, f"{RATA_URI}#Neural_Model1", "/tmp/other amp.nam")
    after = chunk.serialize(doc).splitlines()
    check("chunk: set_state reports a change", changed is True, repr(changed))
    diff = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    check("chunk: set_state touches exactly one line", len(diff) == 1, str(diff))
    check("chunk: set_state quotes a path containing a space",
          '"/tmp/other amp.nam"' in after[diff[0]] if diff else False,
          after[diff[0]] if diff else "")
    check("chunk: set_state preserves the trailing flags field",
          after[diff[0]].rstrip().endswith(" 3") if diff else False,
          after[diff[0]] if diff else "")

    reread = chunk.get_state(rata)
    check("chunk: edited value reads back",
          reread[f"{RATA_URI}#Neural_Model1"] == "/tmp/other amp.nam",
          repr(reread[f"{RATA_URI}#Neural_Model1"]))

    # Clearing a slot must emit the bare word None, not an empty string.
    chunk.set_state(doc, rata, f"{RATA_URI}#Neural_Model1", "")
    cleared = [l for l in chunk.serialize(doc).splitlines()
               if "Neural_Model1" in l]
    check("chunk: clearing a slot writes None",
          bool(cleared) and cleared[0].split()[-2] == "None", str(cleared))

    missing, err = chunk.set_state(doc, rata, "urn:nope#absent", "x")
    check("chunk: unknown <STATE> key is reported",
          missing is False and err is not None, repr(err))


SAMPLE_CFG = """{
  "schema": 1,
  "title": "RBJ 1073",
  "color": "#2b6f76",
  "wet_label": "Wet",
  "on_label": "On",
  "controls": {
    "knobs": [
      {"index": 2, "label": "Low", "type": "continuous"},
      {"index": 3, "label": "Mid Hz", "type": "discrete", "ticks": ["360", "700", "1.6k", "3.2k", "4.8k", "7.2k"]},
      {"index": 4, "label": "Mid", "type": "continuous"},
      {"index": 5, "label": "High", "type": "continuous"},
      {"index": 6, "label": "Gain", "type": "continuous"}
    ],
    "switches": [
      {"index": 8, "label": "HPF", "type": "multi", "ticks": ["Off", "50", "80", "160", "300"]},
      {"index": 9, "label": "Lo Hz", "type": "multi", "ticks": ["Off", "35", "60", "110", "220"]}
    ]
  }
}"""


def test_panel() -> None:
    lua = make_runtime()
    panel = require(lua, "skel_lib.panel")
    cfg = panel.parse(SAMPLE_CFG)
    check("panel: title", cfg["title"] == "RBJ 1073", repr(cfg["title"] if cfg else cfg))
    check("panel: color_hex", cfg["color_hex"] == "#2b6f76", repr(cfg["color_hex"] if cfg else cfg))
    knobs = cfg["knobs"]
    n_knobs = sum(1 for i in range(1, 8) if knobs[i] is not None)
    check("panel: 5 knobs", n_knobs == 5, str(n_knobs))
    check("panel: k2 discrete", knobs[2]["type"] == "discrete" and knobs[2]["label"] == "Mid Hz")
    check("panel: k2 param", knobs[2]["param"] == 3, repr(knobs[2]["param"]))
    steps = [knobs[2]["steps"][i] for i in range(1, 4)]
    check("panel: mid ticks", steps == ["360", "700", "1.6k"], str(steps))
    switches = cfg["switches"]
    n_sw = sum(1 for i in range(1, 5) if switches[i] is not None)
    check("panel: 2 switches", n_sw == 2, str(n_sw))
    check("panel: s1 multi", switches[1]["type"] == "multi" and switches[1]["label"] == "HPF")
    hpf = [switches[1]["steps"][i] for i in range(1, 6)]
    check("panel: hpf ticks", hpf == ["Off", "50", "80", "160", "300"], str(hpf))

    wrapped = "junk prefix\n" + SAMPLE_CFG
    extracted = panel.extract(wrapped)
    check("panel: extract JSON after junk", extracted.startswith("{"), repr(extracted)[:40])
    decoded = panel.b64decode(panel_b64 := __import__("base64").b64encode(SAMPLE_CFG.encode()).decode())
    check("panel: b64 roundtrip", decoded.startswith("{"), repr(decoded)[:40])
    blob = "sliders here\n" + panel_b64
    got = panel.extract(blob)
    check("panel: extract from base64", bool(got) and "RBJ 1073" in got, repr(got)[:60])
    check("panel: parse b64 chunk", panel.parse(blob)["title"] == "RBJ 1073")
    check("panel: ignore empty", panel.parse("") is None)
    check("panel: ignore noise", panel.parse("1 0.5 0.2 - - -") is None)
    check("panel: ignore other kind", panel.parse('{"kind":"amp","title":"X"}') is None)
    check("panel: reject old comment", panel.parse('{"kind":"pedal","title":"Old","color":4,"knobs":[]}') is None)
    comma = '{"schema":1,"title":"X","color":"#aabbcc","wet_label":"Wet","on_label":"On","controls":{"knobs":[{"index":2,"label":"A","type":"discrete","ticks":["700 Hz, wide","1.6k"]},{"index":3,"label":"B","type":"continuous"}],"switches":[]}}'
    comma_cfg = panel.parse(comma)
    check("panel: tick with comma", comma_cfg["knobs"][1]["steps"][1] == "700 Hz, wide",
          repr(comma_cfg["knobs"][1]["steps"][1] if comma_cfg else None))
    encoded, err = panel.to_json(panel.parse_wire(comma))
    check("panel: encode roundtrip comma", bool(encoded) and "700 Hz, wide" in encoded, repr(err or encoded)[:80])
    check("panel: is_pedal ident", panel.is_pedal("", "JS:Skeletons/skel_panel_pedal") is True)
    check("panel: is_pedal name", panel.is_pedal("JS: Skeletons Pedal", "") is True)
    check("panel: is_pedal legacy ident", panel.is_pedal("", "JS:ReaperAPP/rapp_panel_pedal") is True)
    check("panel: is_pedal legacy name", panel.is_pedal("JS: ReaperAPP Pedal", "") is True)
    check("panel: skip unrelated", panel.is_pedal("ReaEQ", "vst") is False)
    hole = panel.parse_wire(comma)
    hole["controls"]["knobs"][1]["ticks"] = lua.table_from(["A", "", "C"])
    _ok, hole_err = panel.validate(hole)
    check("panel: reject empty tick in the middle", _ok is None and "middle" in str(hole_err),
          repr(hole_err))


def main() -> int:
    if not TEMPLATE.is_file():
        sys.exit(f"template not found: {TEMPLATE}")
    print("== json.lua ==")
    test_json()
    print("\n== chunk.lua ==")
    test_chunk()
    print("\n== panel.lua ==")
    test_panel()
    print()
    if failures:
        print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
