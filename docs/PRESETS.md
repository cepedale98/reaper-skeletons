# Preset and bank schema

This is the written contract the Lua agent and the GTK apps share. A command
on the wire is only an **id**; the agent reads the JSON from disk because the
HTTP surface truncates each ExtState value at 1024 bytes.

Two tiers, which is the core of the design.

## Bank (`banks/<id>.json`)

A bank is the set of `.nam` models and `.wav` IRs **resident** in Ratatouille
slots. Changing residency costs the plugin's internal ~90 ms dropout (fade,
two blocking waits, parse, warm-up). IR swaps are worse.

```json
{
  "id": "cleantonic",
  "label": "Cleantonic AME",
  "slots": {
    "<role>": {
      "fx_slot": 0,
      "A": { "model": "/abs/path.nam", "ir": "/abs/path.wav" },
      "B": { "model": null, "ir": "/abs/path.wav" }
    }
  }
}
```

| Field | Type | Meaning |
| ----- | ---- | ------- |
| `id` | string | Filename stem; unique across `banks/` |
| `label` | string | Browser text |
| `slots` | object | Keyed by `P_EXT:skel_role` |
| `fx_slot` | int? | Ratatouille index on that track; default = first match |
| `A` / `B` | object | Slot residency. `null` / omit = leave that field alone. `false` would mean clear (not used in shipped banks). |
| `model` / `ir` | string \| null | Absolute path, or `null` for empty |

`buffered` (port 20) is **not** in the bank. It is pinned to `1` on every
instance (see `docs/PDC.md`) because it changes reported latency.

## Preset (`presets/<instrument>/<id>.json`)

A preset is everything reachable **without** changing residency: smoothed
Ratatouille ports, REAPER-native FX presets, normalised parameters, track
volume, parallel send level, bypass flags.

```json
{
  "id": "cleantonic",
  "label": "Cleantonic AME MIX",
  "bank": "cleantonic",
  "category": "Clean",
  "character": ["Compressed"],
  "slots": {
    "<role>": {
      "volume_db": 0,
      "pan": 0,
      "mute": false,
      "send_db": -8,
      "fx": [
        {
          "slot": 0,
          "ident": "urn:brummer:ratatouille",
          "match": "Ratatouille",
          "label": "Amp",
          "bypass": false,
          "preset": "My LV2 preset",
          "ratatouille": {
            "blend": 0.43,
            "ir_mix": 0.86,
            "input_a": -0.6,
            "input_b": -5.2,
            "output": 12
          },
          "params": { "0": 0.5 },
          "key_params": ["blend", "ir_mix", "input_a", "input_b", "output"]
        }
      ]
    }
  }
}
```

| Field | Type | Meaning |
| ----- | ---- | ------- |
| `bank` | string | Required bank id. Missing bank ⇒ always instant. |
| `volume_db` | number | Track fader, ramped ~50 ms |
| `send_db` | number | First hardware-send / bus send, ramped ~50 ms |
| `fx[].slot` | int | 0-based `TrackFX_*` index |
| `fx[].ident` / `match` | string | Must match live plugin or the entry is skipped |
| `fx[].bypass` | bool | Preset-time only. Never used to cover a switch (PDC click). |
| `fx[].preset` | string \| int | `TrackFX_SetPreset` / `SetPresetByIndex` |
| `fx[].ratatouille` | object | Raw units (dB / 0–1). `buffered` and `phase` are refused. |
| `fx[].params` | object | Normalised 0–1, keyed by parameter index |
| `fx[].key_params` | list | Whitelist the GTK knobs draw. Names for Ratatouille, ints otherwise. |

## Classifying a transition

Given the currently resident bank (from live `<STATE>` vs `banks/*.json`) and
the preset the user just picked:

| Situation | Badge | Path |
| --------- | ----- | ---- |
| `preset.bank` is empty or already resident | **instant** | Set smoothed Ratatouille ports directly; software-ramp unsmoothed JSFX params over 20–50 ms |
| Bank differs, target slot is blended away (`blend` ≤ 0.02 or ≥ 0.98) | **arming** | Load into the silent slot (~90 ms hole, inaudible), wait `LOAD_SETTLE_SECONDS` (0.45 s), then crossfade `blend` over 120 ms |
| Bank differs, both slots audible | **arming** | Park blend to the nearer side, optional cover-mute 60 ms, then the same as above |

The browser always shows the badge **before** the click so the behaviour is
never a surprise. Classification is `skeletons.presets.classify_transition`.

## Rules that protect the switch

1. Never vary `buffered`. It changes PDC and forces a graph resync.
2. Never toggle FX bypass to hide a load. Bypass changes compensation and clicks.
3. Commands carry only the preset id. The agent reads the file.
4. High-rate knob writes go over OSC, not ExtState.

## FX-chain rigs (separate from presets)

Loading plugins onto the skeleton is `load_rig`: a folder of `.RfxChain` files
under `fxchains/<instrument>/<rig>/`. That instantiates (or replaces) hosted
FX. Presets above assume the chain is already there and only move parameters.
The GTK Amp/Cab tabs bind to whatever Ratatouille is resident after the rig
load; Control JSFX sliders remain the Param-linked surface for everything else.
