# PDC and the `buffered` pin

Ratatouille's `buffered` port (LV2 symbol `buffered`, typically parameter 15)
changes the latency the plugin reports to REAPER. If two instances disagree, or
a preset varies the value, REAPER recomputes delay compensation for the whole
graph. That resync is audible.

The rule: **every Ratatouille instance, in every preset, holds the same
`buffered` and `phase` values.**

Pinned values (see `rata.PINNED` in `reaper/skel_lib/ratatouille.lua`):

| control  | value | why |
| -------- | ----- | --- |
| buffered | 1     | slot B runs on a worker thread; buffered mode makes that output deterministic |
| phase    | 0     | structural, not a per-preset tone control |

The Cleantonic template originally had `buffered=0` on INPUT and `buffered=1`
on AMP/CAB. `tools/check_buffered.py --fix` normalised that. The agent also
calls `rata.pin_controls` once at startup.

FX bypass also changes PDC. Bypass is a preset-time setting only and is never
used to cover a switch.
