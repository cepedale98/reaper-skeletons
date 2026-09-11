--[[
  skel_lib/presets.lua -- bank residency and preset application.

  Two tiers, which is the core of the whole design:

    A BANK is the set of .nam models and .wav IRs RESIDENT in the Ratatouille
    slots. Changing residency costs the plugin's internal ~90 ms dropout.

    A PRESET is everything reachable WITHOUT changing residency: the smoothed
    blend and gain ports, plus REAPER-native FX presets and parameter values on
    the VST and JSFX slots.

  So switching preset inside a bank is instant. Switching bank is not, and is
  handled by arming: load the incoming model into whichever slot is currently
  blended away, let it settle, then crossfade. The dropout lands on a slot
  nobody is hearing.

  See docs/PRESETS.md for the file format.
]]

local json  = require('skel_lib.json')
local chunk = require('skel_lib.chunk')
local rata  = require('skel_lib.ratatouille')

local presets = {}

--- Ramp durations, seconds. Short enough to feel immediate, long enough that a
--- coefficient recalculation inside a JSFX is not heard as a click.
presets.RAMP_PARAM   = 0.035
presets.RAMP_VOLUME  = 0.050
presets.RAMP_BLEND   = 0.120  -- the audible amp crossfade; deliberately slower
presets.RAMP_COVER   = 0.060  -- mute cover for a disruptive bank change

----------------------------------------------------------------------
-- loading from disk
----------------------------------------------------------------------

local function list_json(dir)
  local out = {}
  local i = 0
  while true do
    local name = reaper.EnumerateFiles(dir, i)
    if not name then break end
    if name:lower():match('%.json$') then out[#out + 1] = name end
    i = i + 1
  end
  table.sort(out)
  return out
end

--- Read every preset for an instrument from <root>/presets/<instrument>/.
--- Returns list plus a list of load errors, so a single malformed file surfaces
--- in the UI instead of taking the whole browser down.
function presets.load_all(root, instrument)
  local dir = root .. '/presets/' .. instrument
  local list, errors = {}, {}
  for _, name in ipairs(list_json(dir)) do
    local data, err = json.decode_file(dir .. '/' .. name)
    if data then
      data.id = data.id or name:gsub('%.json$', '')
      data.__file = dir .. '/' .. name
      list[#list + 1] = data
    else
      errors[#errors + 1] = err
    end
  end
  table.sort(list, function(a, b)
    return (a.label or a.id or '') < (b.label or b.id or '')
  end)
  return list, errors
end

function presets.load_banks(root)
  local dir = root .. '/banks'
  local by_id, errors = {}, {}
  for _, name in ipairs(list_json(dir)) do
    local data, err = json.decode_file(dir .. '/' .. name)
    if data then
      data.id = data.id or name:gsub('%.json$', '')
      by_id[data.id] = data
    else
      errors[#errors + 1] = err
    end
  end
  return by_id, errors
end

----------------------------------------------------------------------
-- residency comparison
----------------------------------------------------------------------

local function same_path(a, b)
  if a == nil and b == nil then return true end
  if a == nil or b == nil then return false end
  return a == b
end

--- Compare a bank's required residency against what is actually loaded.
---
--- Returns:
---   resident  true when every slot already holds the required file
---   diffs     list of { role, fx, slot, field, want, have }
function presets.residency_diff(bank, resolved)
  local diffs = {}
  if not bank or not bank.slots then return true, diffs end

  for role, spec in pairs(bank.slots) do
    local hit = resolved[role]
    if hit then
      local fx = presets.find_ratatouille(hit.track, spec.fx_slot)
      if fx then
        local have = rata.read_residency(hit.track, fx)
        if have then
          for _, slot_id in ipairs({ 'A', 'B' }) do
            local want = spec[slot_id]
            if want then
              local have_model = slot_id == 'A' and have.model_a or have.model_b
              local have_ir    = slot_id == 'A' and have.ir_a    or have.ir_b
              if want.model ~= nil and not same_path(want.model, have_model) then
                diffs[#diffs + 1] = { role = role, fx = fx, slot = slot_id,
                  field = 'model', want = want.model, have = have_model }
              end
              if want.ir ~= nil and not same_path(want.ir, have_ir) then
                diffs[#diffs + 1] = { role = role, fx = fx, slot = slot_id,
                  field = 'ir', want = want.ir, have = have_ir }
              end
            end
          end
        end
      end
    end
  end

  return #diffs == 0, diffs
end

--- First Ratatouille instance on a track, or the given index when pinned by the
--- bank file. Returns nil when the track has none.
function presets.find_ratatouille(track, pinned)
  if pinned ~= nil then
    if rata.is_ratatouille(track, pinned) then return pinned end
    return nil
  end
  for fx = 0, reaper.TrackFX_GetCount(track) - 1 do
    if rata.is_ratatouille(track, fx) then return fx end
  end
  return nil
end

----------------------------------------------------------------------
-- applying a preset
----------------------------------------------------------------------

local function db_to_gain(db)
  if db == nil then return nil end
  if db <= -150 then return 0 end
  return 10 ^ (db / 20)
end

--- Verify a preset's FX entry actually points at the plugin it claims.
--- A mismatch means the chain was edited underneath us; we skip rather than
--- writing parameters into the wrong plugin.
local function fx_matches(track, fx, entry)
  if reaper.TrackFX_GetCount(track) <= fx then return false, 'slot absent' end
  if entry.ident then
    local ok, ident = reaper.TrackFX_GetNamedConfigParm(track, fx, 'fx_ident')
    if ok and ident and ident ~= '' then
      if not ident:find(entry.ident, 1, true) then
        return false, string.format('expected %s, found %s', entry.ident, ident)
      end
      return true
    end
  end
  if entry.match then
    local _, name = reaper.TrackFX_GetFXName(track, fx, '')
    if not (name or ''):lower():find(entry.match:lower(), 1, true) then
      return false, string.format('expected %s, found %s', entry.match, name or '?')
    end
  end
  return true
end

local function apply_fx_entry(ctx, track, role, fx, entry, warnings)
  local ok, why = fx_matches(track, fx, entry)
  if not ok then
    warnings[#warnings + 1] = string.format('%s FX %d: %s', role, fx, why)
    return
  end

  if entry.bypass ~= nil then
    -- Bypass changes PDC compensation, so it is a preset-time setting only and
    -- is never used to cover a switch.
    reaper.TrackFX_SetEnabled(track, fx, not entry.bypass)
  end

  if entry.preset ~= nil then
    if type(entry.preset) == 'number' then
      reaper.TrackFX_SetPresetByIndex(track, fx, math.floor(entry.preset))
    elseif type(entry.preset) == 'string' and entry.preset ~= '' then
      reaper.TrackFX_SetPreset(track, fx, entry.preset)
      -- SetPreset silently no-ops on a name mismatch (some plugins pad names),
      -- so confirm rather than trusting the return value.
      local _, current = reaper.TrackFX_GetPreset(track, fx, '')
      if current ~= entry.preset then
        warnings[#warnings + 1] = string.format(
          '%s FX %d: preset %q did not take (now %q)', role, fx, entry.preset, current or '')
      end
    end
  end

  -- Ratatouille's logical controls, written as raw values in their own units.
  if entry.ratatouille then
    for control, value in pairs(entry.ratatouille) do
      if rata.PINNED[control] ~= nil then
        -- Refused rather than clamped. `buffered` changes reported latency, so
        -- a preset that varies it would force a PDC resync mid-performance.
        warnings[#warnings + 1] = string.format(
          '%s FX %d: refused to set pinned control %q (see docs/PDC.md)',
          role, fx, control)
      elseif type(value) == 'number' then
        local key = string.format('%s:%d:%s', role, fx, control)
        local duration = rata.SMOOTHED[control] and 0 or presets.RAMP_PARAM
        if control == 'blend' or control == 'ir_mix' then
          duration = presets.RAMP_BLEND
        end
        local current = rata.get(track, fx, control)
        ctx.ramps:add(key, function(v)
          rata.set(track, fx, control, v)
        end, current, value, duration)
      end
    end
  end

  -- Generic normalised parameters, addressed by index.
  if entry.params then
    for index_str, value in pairs(entry.params) do
      local index = tonumber(index_str)
      if index and type(value) == 'number' then
        local key = string.format('%s:%d:p%d', role, fx, index)
        local current = reaper.TrackFX_GetParamNormalized(track, fx, index)
        ctx.ramps:add(key, function(v)
          reaper.TrackFX_SetParamNormalized(track, fx, index, v)
        end, current, value, presets.RAMP_PARAM)
      end
    end
  end
end

local function apply_slot(ctx, role, spec, resolved, warnings)
  local hit = resolved[role]
  if not hit then
    warnings[#warnings + 1] = 'missing track for role ' .. role
    return
  end
  local track = hit.track

  if spec.volume_db ~= nil then
    local target = db_to_gain(spec.volume_db)
    local current = reaper.GetMediaTrackInfo_Value(track, 'D_VOL')
    ctx.ramps:add(role .. ':vol', function(v)
      reaper.SetMediaTrackInfo_Value(track, 'D_VOL', v)
    end, current, target, presets.RAMP_VOLUME)
  end

  if spec.pan ~= nil then
    reaper.SetMediaTrackInfo_Value(track, 'D_PAN', spec.pan)
  end

  if spec.mute ~= nil then
    reaper.SetMediaTrackInfo_Value(track, 'B_MUTE', spec.mute and 1 or 0)
  end

  -- Level of this track's first send, used for the parallel feed into the
  -- reverb / SideFX bus.
  if spec.send_db ~= nil and reaper.GetTrackNumSends(track, 0) > 0 then
    local target = db_to_gain(spec.send_db)
    local current = reaper.GetTrackSendInfo_Value(track, 0, 0, 'D_VOL')
    ctx.ramps:add(role .. ':send0', function(v)
      reaper.SetTrackSendInfo_Value(track, 0, 0, 'D_VOL', v)
    end, current, target, presets.RAMP_VOLUME)
  end

  if spec.fx then
    for i = 1, #spec.fx do
      local entry = spec.fx[i]
      local fx = entry.slot
      if fx == nil then
        warnings[#warnings + 1] = role .. ': FX entry has no slot index'
      else
        apply_fx_entry(ctx, track, role, math.floor(fx), entry, warnings)
      end
    end
  end
end

--- Apply the non-residency half of a preset. Never blocks: every value change
--- is handed to the ramp scheduler and completes over subsequent defer ticks.
function presets.apply(ctx, preset, resolved)
  local warnings = {}
  if not preset or not preset.slots then
    return false, { 'preset has no slots' }
  end
  for role, spec in pairs(preset.slots) do
    apply_slot(ctx, role, spec, resolved, warnings)
  end
  return true, warnings
end

----------------------------------------------------------------------
-- arming: making a bank resident
----------------------------------------------------------------------

--- Plan the residency changes a bank needs, grouped so each Ratatouille
--- instance is written once.
---
--- Returns a list of steps:
---   { role, fx, slot, model, ir, hideable }
--- `hideable` is true when the target slot is currently blended away, which is
--- what makes the plugin's dropout inaudible.
function presets.plan_arming(bank, resolved)
  local _, diffs = presets.residency_diff(bank, resolved)
  local grouped, order = {}, {}

  for _, diff in ipairs(diffs) do
    local key = diff.role .. ':' .. diff.fx .. ':' .. diff.slot
    if not grouped[key] then
      grouped[key] = { role = diff.role, fx = diff.fx, slot = diff.slot }
      order[#order + 1] = key
    end
    grouped[key][diff.field] = diff.want
  end

  local steps = {}
  for _, key in ipairs(order) do
    local step = grouped[key]
    local hit = resolved[step.role]
    if hit then
      local away = rata.away_slot(hit.track, step.fx)
      step.hideable = (away == step.slot)
      steps[#steps + 1] = step
    end
  end
  return steps
end

--- Execute one arming step. Returns ok, message, elapsed_ms.
---
--- When the step is not hideable the caller should have covered it with a mute;
--- we still perform it, but say so, because an honest deliberate gap beats an
--- unpredictable glitch.
function presets.arm_step(step, resolved)
  local hit = resolved[step.role]
  if not hit then return nil, 'missing track for ' .. step.role end
  return rata.load_slot(hit.track, step.fx, step.slot, step.model, step.ir)
end

return presets
