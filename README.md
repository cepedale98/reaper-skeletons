# Skeletons

GTK 4 control surfaces for a permanently running REAPER instance. The apps
are an interface: REAPER hosts every plugin, loads its own `.RTrackTemplate`
and `.RfxChain` files, and owns the audio. The GTK windows only drive
parameters you expose through **Skeletons Control** (`skel_control.jsfx`) and
Live-view pedals (`skel_panel_pedal.jsfx`).

## How a guitar rig is assembled

1. Open `project/Skeletons.RPP`, or in REAPER insert
   `TrackTemplates/SkeletonsGuitar/SkeletonsGuitar.RTrackTemplate`. Tracks are named
   **Skeletons Guitar / IN / PEDALS / AMP / CAB / FX** and tagged `P_EXT:skel_role`.
   IN already has Control plus a dry tuner and scope. Other tabs start with
   Control; hosted FX come from chain files.
2. Each tab loads and saves a `.RfxChain` in REAPER's native tree:

   ```
   FXChains/SkeletonsGuitar/IN/*.RfxChain
   FXChains/SkeletonsGuitar/PEDALS/*.RfxChain
   FXChains/SkeletonsGuitar/AMP/*.RfxChain
   FXChains/SkeletonsGuitar/CAB/*.RfxChain
   FXChains/SkeletonsGuitar/FX/*.RfxChain
   ```

   In extended mode, pick a chain, **Load** it onto that skeleton track, tweak
   in REAPER or on the GTK cards, then **Save** back into the same folder.
3. Param-link Control sliders to the hosted FX. Rename sliders in the JSFX if
   you want those names in GTK. Control / tuner / scope / live are kept on the
   track and are not written into saved chain files.
4. Live ON draws one widget per **Skeletons Pedal** JSFX on the current tab.
   Param-link its sliders. Layout JSON (`schema: 1`) is written into that FX's
   **Comments** field by the Pedal Panel Editor (title, `#rrggbb` color,
   discrete knobs, multi-state switches). Live ON is display-only for the
   layout; turning a live knob only writes the 0–1 slider value.

Keyboard, Microphone, SideFX and Looper launchers exist as stubs sharing the
same library and the same REAPER instance. Every non-Settings window has a
**SETTINGS** button that opens the environment app in its own process.

## Settings

`python3 -m apps.settings` (or the desktop entry, or the SETTINGS button in
Skeletons Guitar / Keyboard / Microphone / SideFX / Looper) points the environment at:

- REAPER resource and install folders
- Track group templates (`.RTrackTemplate`, including `TrackTemplates/SkeletonsGuitar/`)
- FX chain templates (`FXChains/SkeletonsGuitar/IN` … `FX`)
- REAPER track icons
- Environment-owned `assets/` (icons, skins, fonts)

Saving publishes those paths to the running agent over HTTP ExtState.

## Install

From the checkout:

```
python3 -m skeletons install
python3 -m skeletons check
./launch.sh                 # Skeletons Guitar
./launch.sh apps.settings
```

`install` writes the skeleton templates, copies Lua / JSFX / OSC / SkeletonsGuitar
into the REAPER resource folder (`~/.config/REAPER` by default), seeds
`FXChains/SkeletonsGuitar/<TAB>/cleantonic.RfxChain`, makes `__startup.lua` load the
agent, adds HTTP and OSC surfaces if they are missing, and writes desktop
launchers.

After a previous **ReaperAPP** install, run `./cleanup.sh` so old
`Scripts/ReaperAPP`, `Effects/ReaperAPP`, and `reaperapp-*.desktop` files do not
shadow the new idents. `./uninstall.sh` removes the current Skeletons copies
(scripts, JSFX, OSC, desktop launchers) without deleting your `.RfxChain` rigs.

Keep REAPER's HTTP control surface on port 8080. Restart REAPER after install so
`__startup.lua` loads `Scripts/Skeletons/skel_agent.lua`.

To edit a pedal panel: Actions → Show action list → New action → Load ReaScript →
`Scripts/Skeletons/skel_panel_editor.lua`. Bind that action to a toolbar if you
want. If the action errors, install ReaPack **ReaImGui: ReaScript binding for
Dear ImGui** and restart REAPER.

Other commands: `python3 -m skeletons export`, `build`, `status`, `paths`,
`uninstall`, `cleanup`. Version is `0.1.0` (see `VERSION`). The deprecated
`./reaperapp` wrapper still forwards to `python3 -m skeletons`.

These apps need **GTK 4** and **Gdk 4** (pinned in `skeletons/gi_init.py` before
any `gi.repository` import).
