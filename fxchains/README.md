# FX chain templates

Install copies these files into REAPER's native FXChains tree, one folder per
app and tab:

```
~/.config/REAPER/FXChains/SkeletonsGuitar/
  IN/*.RfxChain
  PEDALS/*.RfxChain
  AMP/*.RfxChain
  CAB/*.RfxChain
  FX/*.RfxChain
```

The same stem across tabs is a **rig** (for example `cleantonic.RfxChain` in
each folder). Load one tab at a time from the Guitar extended-mode bar, or
load the matching stem on every tab with `load_rig`. Saving a tab writes only
the hosted plugins; Skeletons Control, tuner, scope and live stay on the track.

This checkout still keeps extracted examples under
`fxchains/guitar/cleantonic/` (`input.RfxChain`, …). `python3 -m skeletons install`
copies them to `FXChains/SkeletonsGuitar/<TAB>/cleantonic.RfxChain` if that file is
not already there, so later installs do not overwrite a chain you saved from
the app.

Track templates land in `TrackTemplates/SkeletonsGuitar/SkeletonsGuitar.RTrackTemplate`.
