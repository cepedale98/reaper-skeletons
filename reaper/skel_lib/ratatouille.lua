--[[
  skel_lib/ratatouille.lua -- the amp switching mechanism.

  Ratatouille (LV2, brummer) holds two neural model slots and two IR slots, and
  crossfades between them. Reading its engine.h, the crossfade and gain ports
  are each run through a per-sample one-pole:

      fRec2[0] = fSlow2 + 0.999 * fRec2[1];
      output[i] = bufa[i] * (1.0 - fRec2[0]) + bufb[i] * fRec2[0];

  so moving `blend` from a script is smooth by construction. That makes blending
  between two ALREADY-RESIDENT models the only glitch-free way to change amp
  voice, and it is what the fast path uses.

  Changing which file is resident is the opposite: NeuralModel::loadModel()
  fades out over 256 samples, blocks 30 ms, sets ready=false so the realtime
  thread emits silence, blocks a further 60 ms, then parses the .nam from disk
  and runs a 4096-sample warm-up. That is a ~90 ms floor which lives inside the
  plugin, so no host API avoids it. The arming path therefore loads into
  whichever slot is currently blended away.

  Parameters are resolved by name, never by hardcoded index, because REAPER may
  report either the LV2 symbol or the lv2:name and may or may not include the
  output-only ports.
]]

local chunk = require('skel_lib.chunk')

local rata = {}

rata.URI = 'urn:brummer:ratatouille'

--- Control-port order as REAPER serialises it in the chunk's `P` lines. Output
--- ports (latency, ms_latency, Xrun) are absent there, which is what lets
--- resolve_params tell the two possible parameter layouts apart.
rata.CONTROL_ORDER = {
  'input_a',       -- Knob0, -20..20 dB, smoothed
  'output',        -- Knob1, -20..20 dB, smoothed
  'blend',         -- Knob2, 0..1, smoothed. 0 = slot A only, 1 = slot B only
  'ir_mix',        -- Knob3, 0..1, smoothed. 0 = IR A only, 1 = IR B only
  'delay',         -- Knob4, -4096..4096 samples, NOT smoothed
  'ir_norm_a',     -- NormalizeA
  'ir_norm_b',     -- NormalizeB
  'input_b',       -- Knob5, -20..20 dB, smoothed
  'model_norm_a',  -- NormalizeSlotA
  'model_norm_b',  -- NormalizeSlotB
  'enable',        -- ENABLE
  'erase_model_a', -- eraseSlotA
  'erase_model_b', -- eraseSlotB
  'erase_ir_a',    -- eraseIr
  'erase_ir_b',    -- eraseIr1
  'buffered',      -- changes reported latency: must stay constant across presets
  'phase',
}

--- Candidate parameter names per control: the LV2 symbol first, then the
--- lv2:name. Matching is exact and case-insensitive, so `input` never collides
--- with `input1`.
rata.CANDIDATES = {
  input_a       = { 'Knob0', 'input' },
  output        = { 'Knob1', 'output' },
  blend         = { 'Knob2', 'blend', 'blend(A|B)' },
  ir_mix        = { 'Knob3', 'mix', 'mix (IR)', 'mix(IR)' },
  delay         = { 'Knob4', 'Delay' },
  ir_norm_a     = { 'NormalizeA', 'Normalize A' },
  ir_norm_b     = { 'NormalizeB', 'Normalize B' },
  input_b       = { 'Knob5', 'input1' },
  model_norm_a  = { 'NormalizeSlotA', 'Normalize Slot A' },
  model_norm_b  = { 'NormalizeSlotB', 'Normalize Slot B' },
  enable        = { 'ENABLE', 'enable' },
  erase_model_a = { 'eraseSlotA', 'erase Slot A' },
  erase_model_b = { 'eraseSlotB', 'erase Slot B' },
  erase_ir_a    = { 'eraseIr', 'erase Ir' },
  erase_ir_b    = { 'eraseIr1', 'erase Ir1' },
  buffered      = { 'buffered', 'Buffered' },
  phase         = { 'phase', 'Phase Correction' },
}

--- Controls whose value is interpolated inside the plugin, and so are safe to
--- write directly while audio is passing.
rata.SMOOTHED = {
  input_a = true, output = true, blend = true, ir_mix = true, input_b = true,
}

--- Controls that must hold the same value on every instance in every preset.
---
--- `buffered` changes the plugin's reported latency, so varying it forces
--- REAPER to recompute delay compensation for the whole graph mid-performance
--- -- an audible resync. The Cleantonic template disagrees with itself today:
--- buffered=0 on the INPUT instance, buffered=1 on the AMP/CAB one.
---
--- Pinned to 1 because the design keeps both model slots loaded and slot B runs
--- on its own thread; buffered mode is what makes that thread's output
--- available deterministically instead of racing the block deadline. The cost
--- is one buffer of latency (2.7 ms at 128 samples / 48 kHz) which, being
--- constant, never causes a resync.
---
--- `phase` is pinned for the same reason: it is a structural property of the
--- rig, not a per-preset tone control.
rata.PINNED = {
  buffered = 1,
  phase = 0,
}

--- Per-slot addressing. `model` and `ir` are <STATE> URIs, not parameters.
rata.SLOTS = {
  A = {
    model = rata.URI .. '#Neural_Model',
    ir    = rata.URI .. '#irfile',
    gain  = 'input_a',
    model_norm = 'model_norm_a',
    ir_norm    = 'ir_norm_a',
    erase_model = 'erase_model_a',
    erase_ir    = 'erase_ir_a',
    blend_value = 0.0, -- blend position at which this slot is alone
  },
  B = {
    model = rata.URI .. '#Neural_Model1',
    ir    = rata.URI .. '#irfile1',
    gain  = 'input_b',
    model_norm = 'model_norm_b',
    ir_norm    = 'ir_norm_b',
    erase_model = 'erase_model_b',
    erase_ir    = 'erase_ir_b',
    blend_value = 1.0,
  },
}

rata.STATE_KEYS = {
  model_a = rata.URI .. '#Neural_Model',
  model_b = rata.URI .. '#Neural_Model1',
  ir_a    = rata.URI .. '#irfile',
  ir_b    = rata.URI .. '#irfile1',
}

----------------------------------------------------------------------
-- identification and parameter resolution
----------------------------------------------------------------------

function rata.is_ratatouille(track, fx)
  local ok, ident = reaper.TrackFX_GetNamedConfigParm(track, fx, 'fx_ident')
  if ok and ident and ident:find(rata.URI, 1, true) then return true end
  local _, name = reaper.TrackFX_GetFXName(track, fx, '')
  return (name or ''):lower():find('ratatouille', 1, true) ~= nil
end

local resolve_cache = {}

local function cache_key(track, fx)
  return tostring(track) .. ':' .. tostring(fx)
end

--- Map logical control name -> 0-based parameter index.
--- Returns (map, method) where method is 'name', 'positional' or 'positional+outputs',
--- so callers and the probe can tell how much to trust the result.
function rata.resolve_params(track, fx, force)
  local key = cache_key(track, fx)
  if not force and resolve_cache[key] then
    local hit = resolve_cache[key]
    return hit.map, hit.method
  end

  local nparams = reaper.TrackFX_GetNumParams(track, fx)
  local by_name = {}
  for p = 0, nparams - 1 do
    local _, pname = reaper.TrackFX_GetParamName(track, fx, p, '')
    if pname and pname ~= '' then
      by_name[pname:lower()] = p
    end
  end

  local map, matched = {}, 0
  for _, control in ipairs(rata.CONTROL_ORDER) do
    for _, candidate in ipairs(rata.CANDIDATES[control]) do
      local hit = by_name[candidate:lower()]
      if hit then
        map[control] = hit
        matched = matched + 1
        break
      end
    end
  end

  local method = 'name'
  if matched < #rata.CONTROL_ORDER then
    -- Fall back to port order. The two plausible layouts differ by whether the
    -- three output-only ports are exposed, and the count distinguishes them:
    -- 17 controls alone, or 20 with latency / ms_latency / Xrun interleaved
    -- after the erase triggers.
    map = {}
    if nparams >= 20 then
      method = 'positional+outputs'
      local order = {}
      for i, control in ipairs(rata.CONTROL_ORDER) do order[i] = control end
      -- latency sits between erase_ir_b and buffered in LV2 port order.
      local adjusted = {}
      for i = 1, 15 do adjusted[i] = order[i] end
      adjusted[16] = '__latency'
      adjusted[17] = 'buffered'
      adjusted[18] = 'phase'
      for i, control in ipairs(adjusted) do
        if control ~= '__latency' then map[control] = i - 1 end
      end
    else
      method = 'positional'
      for i, control in ipairs(rata.CONTROL_ORDER) do
        map[control] = i - 1
      end
    end
  end

  resolve_cache[key] = { map = map, method = method }
  return map, method
end

function rata.forget(track, fx)
  resolve_cache[cache_key(track, fx)] = nil
end

----------------------------------------------------------------------
-- control read / write
----------------------------------------------------------------------

--- Raw value plus range. Raw is preferable to normalised here because the gain
--- ports are calibrated in dB and the UI shows dB.
function rata.get(track, fx, control)
  local map = rata.resolve_params(track, fx)
  local p = map[control]
  if not p then return nil end
  local value, minv, maxv = reaper.TrackFX_GetParam(track, fx, p)
  return value, minv, maxv, p
end

function rata.set(track, fx, control, value)
  local map = rata.resolve_params(track, fx)
  local p = map[control]
  if not p then return false, 'no such control: ' .. tostring(control) end
  local _, minv, maxv = reaper.TrackFX_GetParam(track, fx, p)
  if minv and maxv and maxv > minv then
    if value < minv then value = minv end
    if value > maxv then value = maxv end
  end
  reaper.TrackFX_SetParam(track, fx, p, value)
  return true
end

--- Fire a `pprop:trigger` port, which Ratatouille uses for its erase buttons.
--- A trigger is momentary, so it is raised and immediately released.
function rata.trigger(track, fx, control)
  local map = rata.resolve_params(track, fx)
  local p = map[control]
  if not p then return false end
  reaper.TrackFX_SetParam(track, fx, p, 1)
  reaper.TrackFX_SetParam(track, fx, p, 0)
  return true
end

----------------------------------------------------------------------
-- slot residency
----------------------------------------------------------------------

--- What is currently loaded, read from the track chunk because the file paths
--- live in <STATE> and are not parameter-addressable.
function rata.read_residency(track, fx)
  local doc, err = chunk.load_track(track)
  if not doc then return nil, err end
  local tnode = chunk.track_node(doc)
  if not tnode then return nil, 'no <TRACK> node' end
  local fx_nodes = chunk.fx_nodes(tnode)
  local node = fx_nodes[fx + 1]
  if not node then return nil, 'FX index ' .. fx .. ' not in chunk' end

  local state = chunk.get_state(node)
  local function clean(v)
    if v == nil or v == 'None' or v == '' then return nil end
    return v
  end
  return {
    model_a = clean(state[rata.STATE_KEYS.model_a]),
    model_b = clean(state[rata.STATE_KEYS.model_b]),
    ir_a    = clean(state[rata.STATE_KEYS.ir_a]),
    ir_b    = clean(state[rata.STATE_KEYS.ir_b]),
  }
end

--- Which slot is inaudible at the current blend position, and therefore safe to
--- load into. Returns slot id ('A'/'B') plus the current blend.
---
--- At blend 0.5 both slots are equally audible and nothing can be hidden, so the
--- caller is told `nil` and must move the blend to one side first.
function rata.away_slot(track, fx, deadzone)
  deadzone = deadzone or 0.02
  local blend = rata.get(track, fx, 'blend')
  if blend == nil then return nil, nil end
  if blend <= deadzone then return 'B', blend end       -- A is alone, hide in B
  if blend >= 1 - deadzone then return 'A', blend end   -- B is alone, hide in A
  return nil, blend
end

function rata.audible_slot(track, fx)
  local away, blend = rata.away_slot(track, fx)
  if not away then return nil, blend end
  return away == 'A' and 'B' or 'A', blend
end

--- Load a model and/or IR into one slot by rewriting its <STATE> entries.
---
--- SetTrackStateChunk is a whole-track write, so whether REAPER preserves the
--- live plugin instance is the open question recorded in docs/FINDINGS.md. Both
--- slots live in the SAME instance, so if REAPER does reinstantiate, the
--- audible slot is affected too -- which is why callers pass cover_mute for
--- bank changes rather than relying on the hiding alone.
---
--- Passing nil for a field leaves it untouched; pass false to clear the slot.
function rata.load_slot(track, fx, slot_id, model, ir)
  local slot = rata.SLOTS[slot_id]
  if not slot then return nil, 'bad slot ' .. tostring(slot_id) end

  local doc, err = chunk.load_track(track)
  if not doc then return nil, err end
  local tnode = chunk.track_node(doc)
  local node = chunk.fx_nodes(tnode)[fx + 1]
  if not node then return nil, 'FX index ' .. fx .. ' not in chunk' end

  local changed = false
  if model ~= nil then
    local value = model == false and '' or model
    if chunk.set_state(doc, node, slot.model, value) then changed = true end
  end
  if ir ~= nil then
    local value = ir == false and '' or ir
    if chunk.set_state(doc, node, slot.ir, value) then changed = true end
  end
  if not changed then return true, 'already resident' end

  local started = reaper.time_precise()
  local ok = reaper.SetTrackStateChunk(track, chunk.serialize(doc), false)
  if not ok then return nil, 'SetTrackStateChunk rejected the chunk' end
  rata.forget(track, fx) -- indices could have moved
  return true, nil, (reaper.time_precise() - started) * 1000
end

----------------------------------------------------------------------
-- readiness
----------------------------------------------------------------------

--- Ratatouille reports its own latency on an output port. If REAPER exposes it
--- as a parameter, a settled value is a genuine readiness signal; otherwise the
--- caller has to fall back to a conservative fixed delay.
function rata.readiness_source(track, fx)
  local nparams = reaper.TrackFX_GetNumParams(track, fx)
  for p = 0, nparams - 1 do
    local _, pname = reaper.TrackFX_GetParamName(track, fx, p, '')
    local lowered = (pname or ''):lower()
    if lowered == 'latency' or lowered == 'ms_latency' then
      return p, pname
    end
  end
  return nil
end

--- Conservative wait before a freshly loaded slot is trusted, in seconds.
--- The plugin's own floor is roughly 90 ms of blocking waits plus the .nam
--- parse and a 4096-sample warm-up, so this leaves generous headroom.
rata.LOAD_SETTLE_SECONDS = 0.45

----------------------------------------------------------------------
-- PDC normalisation
----------------------------------------------------------------------

--- Force every pinned control to its canonical value. Returns a list of the
--- changes made, so the caller can report that the rig was drifting.
---
--- Run at agent startup and from the skeleton builder. Doing it while audio is
--- passing does cause one resync, which is precisely why it happens once at
--- load rather than per preset.
function rata.pin_controls(track, fx)
  local changes = {}
  for control, want in pairs(rata.PINNED) do
    local have = rata.get(track, fx, control)
    if have ~= nil and math.abs(have - want) > 1e-6 then
      rata.set(track, fx, control, want)
      changes[#changes + 1] = { control = control, from = have, to = want }
    end
  end
  return changes
end

--- Report pinned-control drift across every Ratatouille in the project without
--- changing anything.
function rata.audit(resolved)
  local report = {}
  for role, hit in pairs(resolved) do
    for fx = 0, reaper.TrackFX_GetCount(hit.track) - 1 do
      if rata.is_ratatouille(hit.track, fx) then
        for control, want in pairs(rata.PINNED) do
          local have = rata.get(hit.track, fx, control)
          if have ~= nil and math.abs(have - want) > 1e-6 then
            report[#report + 1] = {
              role = role, fx = fx, control = control, have = have, want = want,
            }
          end
        end
      end
    end
  end
  return report
end

return rata
