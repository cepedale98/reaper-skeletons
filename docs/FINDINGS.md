# Spike findings

The probe scripts answer questions that cannot be settled by reading REAPER's
binary. Run them, paste the answers into the "Measured" columns, and adjust the
one config flag each result controls.

```
tools/probe.lua          read-only, safe on the live rig
tools/probe_timing.lua   MODIFIES the project, run muted on a scratch copy
```

Install either through **Actions → Show action list → New action → Load
ReaScript**. Output goes to the ReaScript console and to `skel-probe.txt` /
`skel-probe-timing.txt` in the REAPER resource path.

**Nothing in the codebase blocks on these answers.** Every uncertainty below is
resolved at runtime with a documented fallback, so the apps run correctly before
the probe is ever executed. The probe converts a safe-but-conservative default
into an optimal one.

---

## (a) Where do user FX presets land?

REAPER builds the preset filename by switching on FX type and prefixing `dx-`,
`lv2-`, `js-`, `au-`, `clap-` or `vst-`. The absence of any `lv2-*.ini` in
`presets/` therefore means none has ever been saved, not that LV2 is excluded.

| Question | Prediction | Measured |
| --- | --- | --- |
| Ratatouille preset file | `presets/lv2-urn:brummer:ratatouille.ini` | |
| JSFX ident with a slash, e.g. `sstillwell/1175` | slash creates a subdirectory under `presets/` | |

Read from the `presetfile=` line of `probe.lua` output.

Correction worth recording: `.jsfx-preset` files do not exist. User JSFX presets
go to `presets/js-<name>.ini`; the `.rpl` files shipped beside the effects are
read-only libraries.

## (b) Are Ratatouille's file paths parameter-addressable?

They should **not** be. The `.nam` and `.wav` paths are LV2 patch properties
stored in the chunk's `<STATE>` block, and `TrackFX_SetNamedConfigParm` only
understands `vst_chunk` and `clap_chunk` — there is no LV2 equivalent.

| Question | Prediction | Measured |
| --- | --- | --- |
| `nparams` | 17 controls, or 20 if the output ports are exposed | |
| Any parameter naming a file | none | |
| `fx_type` | `LV2` | |
| `pdc` | non-zero, and it changes with `buffered` | |

This is why `skel_lib/chunk.lua` exists: editing `<STATE>` is the only route to
the file paths.

`ratatouille.resolve_params` handles both parameter layouts. It matches on name
first, accepting either the LV2 symbol (`Knob0`) or the `lv2:name` (`input`),
and only falls back to port order if a name lookup fails — choosing between the
17- and 20-parameter layouts by count. `probe.lua` prints which method fired;
if it ever reports anything other than `name`, add the real names it printed to
`ratatouille.CANDIDATES`.

## (c) Do REAPER-native LV2 presets capture `<STATE>`?

Manual test, described at the end of `probe.lua`'s output: with a `.nam` loaded,
save a preset from the FX window, load a different model, then reselect the
preset.

| Outcome | What it means |
| --- | --- |
| The original `.nam` path returns | LV2 presets carry `<STATE>`. Banks can be authored as REAPER presets. |
| The path does not return | Presets carry parameters only. Residency stays with `chunk.set_state`. |

Measured: _(unrecorded)_

Either way `chunk.set_state` remains the mechanism the agent uses, because a
preset sets **both** slots at once — including the audible one — which defeats
the whole point of arming.

## (d) What does a bank change cost, and does it survive?

The decisive question, and the reason `probe_timing.lua` modifies state.

Both model slots live inside **one** Ratatouille instance. `SetTrackStateChunk`
is a whole-track write, so if REAPER tears the instance down and rebuilds it,
loading into the blended-away slot kills the audible slot too and the arming
trick buys nothing.

`probe_timing.lua` detects this by writing a sentinel into the unused `delay`
parameter and comparing the FX GUID across the write.

| Result | Config | Behaviour |
| --- | --- | --- |
| GUID unchanged **and** sentinel survives | `arming.cover_mute = false` | Bank changes hide in the away slot and are inaudible. |
| Either changes | `arming.cover_mute = true` (**the default**) | Bank changes are wrapped in a ~60 ms ramp down and up: a short deliberate gap instead of an unpredictable click. |

Measured: _(unrecorded — default assumes the pessimistic case)_

The plugin's own floor is unavoidable regardless: `NeuralModel::loadModel()`
fades out over 256 samples, blocks 30 ms, sets `ready = false` so the realtime
thread emits silence, blocks a further 60 ms, parses the `.nam`, then runs a
4096-sample warm-up. That is roughly **90 ms plus real load time**, inside the
plugin, unreachable by any host API. IR swaps are worse: `setIRFile()` waits up
to 160 ms then busy-waits on the convolver thread.

### Readiness signal

Ratatouille publishes `latency`, `ms_latency` and `Xrun` as LV2 **output**
ports. If REAPER exposes them as readable parameters, the agent can poll for a
settled value instead of waiting a fixed interval.

| Question | Prediction | Measured |
| --- | --- | --- |
| `latency` / `ms_latency` readable | unlikely; REAPER usually omits output ports | |

`ratatouille.readiness_source` looks for them and returns `nil` when absent, in
which case the agent waits `rata.LOAD_SETTLE_SECONDS` (0.45 s), generous against
the ~90 ms floor.

---

## Settled without needing the probe

These were resolved by reading sources and are already relied on in code.

**`blend` is smoothed per sample.** `engine.h` runs a one-pole on `Knob0`,
`Knob1`, `Knob2`, `Knob3` and `Knob5`:
`fRec2[0] = fSlow2 + 0.999 * fRec2[1]`. Writing them from a script is
click-free, which is what makes the fast path work.

**`buffered` (port 20) changes reported latency.** Any preset that varies it
forces a PDC resync mid-performance. See `docs/PDC.md`; the skeleton pins it and
`tools/check_buffered.py` audits for drift.

**FX bypass changes PDC too**, so it is never used to cover a switch — doing so
causes the exact click it would be hiding. Bypass is a preset-time setting only,
enforced in `presets.apply`.

**`libgxw` cannot be used from PyGObject.** Fedora's package ships only C
headers and `libgxw.so`, with no `.gir` or `.typelib`. The Cairo widgets are
written from scratch; Guitarix serves as a rendering reference only.
