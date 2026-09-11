--[[
  reaper/skel_agent.lua -- resident defer loop.

  Publishes one JSON state blob per instrument via ExtState and consumes
  per-app command keys so five GTK launchers can share one REAPER instance
  without clobbering each other.

  Commands carry a preset id only; this script reads the JSON from disk because
  the web API truncates each command at 1024 bytes.

  Install: copy to Scripts/Skeletons via tools/install.sh, or Load ReaScript.
  The GTK apps push the workspace path via ExtState (`root`).
]]

-- dofile() from __startup.lua makes get_action_context() point at
-- Scripts/__startup.lua, not this file. Use this chunk's source first.
local function script_dir()
  local src = debug.getinfo(1, 'S').source or ''
  src = src:gsub('^@', '')
  local dir = src:match('^(.*)[/\\]')
  if dir and dir ~= '' and not src:find('__startup%.lua') then
    return dir
  end
  local ctx = select(2, reaper.get_action_context()) or ''
  dir = ctx:match('^(.*)[/\\]')
  if dir and (dir:match('[/\\]Skeletons$') or dir:match('[/\\]ReaperAPP$')) then
    return dir
  end
  return reaper.GetResourcePath() .. '/Scripts/Skeletons'
end

local SCRIPT_DIR = script_dir()
local function detect_checkout()
  return SCRIPT_DIR:match('^(.*)/reaper$')
end
local ROOT = detect_checkout() or SCRIPT_DIR
local installed = reaper.GetResourcePath() .. '/Scripts/Skeletons'
package.path = table.concat({
  SCRIPT_DIR .. '/?.lua',
  SCRIPT_DIR .. '/skel_lib/?.lua',
  installed .. '/?.lua',
  installed .. '/skel_lib/?.lua',
  package.path,
}, ';')

local json     = require('skel_lib.json')
local roles    = require('skel_lib.roles')
local rata     = require('skel_lib.ratatouille')
local presets  = require('skel_lib.presets')
local ramp     = require('skel_lib.ramp')
local chains   = require('skel_lib.chains')
local panel    = require('skel_lib.panel')

local SECTION = 'Skeletons'
local ctx = {
  ramps = ramp.new(),
  last_seq = {},
  current_preset = {},
  current_bank = {},
  current_rig = {},
  current_chain = {},
  arming = nil,
  last_load = nil,
  pending_apply = nil,
  warnings = {},
  started = reaper.time_precise(),
}

local function set_state(key, value)
  reaper.SetExtState(SECTION, key, value, false)
end

local function get_state(key)
  return reaper.GetExtState(SECTION, key)
end

local function root_path()
  local override = reaper.GetExtState(SECTION, 'root')
  if override and override ~= '' then return override end
  return ROOT
end

local function fx_chains_dir()
  local p = get_state('fx_chains')
  if p ~= '' then return p end
  return reaper.GetResourcePath() .. '/FXChains'
end

local function templates_dir()
  local p = get_state('track_templates')
  if p ~= '' then return p end
  return reaper.GetResourcePath() .. '/TrackTemplates'
end

----------------------------------------------------------------------
-- schema / live state
----------------------------------------------------------------------

local function fx_schema(track, fx)
  local _, name = reaper.TrackFX_GetFXName(track, fx, '')
  local _, ident = reaper.TrackFX_GetNamedConfigParm(track, fx, 'fx_ident')
  local _, ftype = reaper.TrackFX_GetNamedConfigParm(track, fx, 'fx_type')
  local _, pset = reaper.TrackFX_GetPreset(track, fx, '')
  local pidx, np = reaper.TrackFX_GetPresetIndex(track, fx)
  local params = json.array({})
  local n = reaper.TrackFX_GetNumParams(track, fx)
  -- Cap published params so the ExtState blob stays well under size limits.
  local cap = math.min(n, 48)
  for i = 0, cap - 1 do
    local _, pname = reaper.TrackFX_GetParamName(track, fx, i, '')
    local _, formatted = reaper.TrackFX_GetFormattedParamValue(track, fx, i, '')
    local pmin, pmax, pstep, ptoggle = 0, 1, 0, false
    if reaper.TrackFX_GetParamEx then
      local _v, mn, mx = reaper.TrackFX_GetParamEx(track, fx, i)
      if type(mn) == 'number' then pmin = mn end
      if type(mx) == 'number' then pmax = mx end
    end
    if reaper.TrackFX_GetParameterStepSizes then
      local okstep, step, _small, _large, istoggle = reaper.TrackFX_GetParameterStepSizes(track, fx, i)
      if okstep then
        if type(step) == 'number' then pstep = step end
        ptoggle = istoggle and true or false
      end
    end
    params[#params + 1] = {
      index = i,
      name = pname or '',
      norm = reaper.TrackFX_GetParamNormalized(track, fx, i),
      text = formatted or '',
      min = pmin,
      max = pmax,
      step = pstep,
      toggle = ptoggle,
    }
  end
  local lname = (name or ''):lower()
  local entry = {
    slot = fx,
    name = name or '',
    ident = ident or '',
    type = ftype or '',
    enabled = reaper.TrackFX_GetEnabled(track, fx),
    preset = pset or '',
    preset_index = pidx,
    preset_count = np,
    nparams = n,
    truncated = n > cap,
    params = params,
    ratatouille = rata.is_ratatouille(track, fx),
    control = lname:find('skel_control', 1, true) ~= nil
      or lname:find('skeletons control', 1, true) ~= nil
      or lname:find('rapp_control', 1, true) ~= nil
      or lname:find('reaperapp control', 1, true) ~= nil,
    live = lname:find('skel_live', 1, true) ~= nil
      or lname:find('skeletons live', 1, true) ~= nil
      or lname:find('rapp_live', 1, true) ~= nil,
    tuner = lname:find('skel_tuner', 1, true) ~= nil
      or lname:find('rapp_tuner', 1, true) ~= nil
      or lname:find('reatune', 1, true) ~= nil,
    scope = lname:find('skel_scope', 1, true) ~= nil
      or lname:find('rapp_scope', 1, true) ~= nil,
    panel = panel.is_pedal(name, ident) and 'pedal' or nil,
  }
  -- Panels are live-view widgets, not utilities: they stay on the track and in chains.
  entry.utility = entry.control or entry.live or entry.tuner or entry.scope
  if entry.panel == 'pedal' then
    entry.panel_cfg = panel.read(track, fx)
  end
  if entry.ratatouille then
    local res = rata.read_residency(track, fx) or {}
    entry.residency = res
    local map = rata.resolve_params(track, fx)
    local controls = {}
    for _, key in ipairs(rata.CONTROL_ORDER) do
      if map[key] then
        controls[key] = rata.get(track, fx, key)
      end
    end
    entry.controls = controls
  end
  return entry
end

local INPUT_FX = {
  { add = 'Skeletons/skel_tuner', needle = 'skel_tuner' },
  { add = 'Skeletons/skel_scope', needle = 'skel_scope' },
}

local BUS_FX = {
  { add = 'Skeletons/skel_control', needle = 'skel_control' },
}

local BUS_REMOVE = { 'skel_tuner', 'skel_scope', 'reatune', 'skel_live', 'rapp_tuner', 'rapp_scope', 'rapp_live' }
local CHILD_REMOVE = { 'skel_control', 'skeletons control', 'skel_live', 'rapp_control', 'reaperapp control', 'rapp_live' }

local TAB_ROLES = {
  'guitar.input', 'guitar.pedals', 'guitar.amp', 'guitar.cabinet', 'guitar.fx',
}

local function find_fx_named(track, needle)
  for fx = 0, reaper.TrackFX_GetCount(track) - 1 do
    local _, name = reaper.TrackFX_GetFXName(track, fx, '')
    if (name or ''):lower():find(needle, 1, true) then
      return fx
    end
  end
  return nil
end

local function delete_named(track, needles)
  for fx = reaper.TrackFX_GetCount(track) - 1, 0, -1 do
    local _, name = reaper.TrackFX_GetFXName(track, fx, '')
    local ident = (name or ''):lower()
    for _, needle in ipairs(needles) do
      if ident:find(needle, 1, true) then
        reaper.TrackFX_Delete(track, fx)
        break
      end
    end
  end
end

local function ensure_named(track, specs)
  for _, spec in ipairs(specs) do
    local fx = find_fx_named(track, spec.needle)
    if fx == nil then
      local idx = reaper.TrackFX_AddByName(track, spec.add, false, 1)
      if idx and idx >= 0 then fx = idx end
    end
    if fx and fx >= 0 then
      reaper.TrackFX_SetEnabled(track, fx, true)
    end
  end
end

--- Tuner/scope on dry IN. Control stays on the folder bus for later panels.
--- Strip leftover per-tab Control and skel_live from older templates.
--- Do not delete Skeletons Pedal JSFX — those are the Live-view pedal widgets.
local function ensure_guitar_utility_fx(resolved)
  local bus = resolved['guitar.bus']
  if bus then
    delete_named(bus.track, BUS_REMOVE)
    ensure_named(bus.track, BUS_FX)
  end
  local input = resolved['guitar.input']
  if input then
    delete_named(input.track, CHILD_REMOVE)
    ensure_named(input.track, INPUT_FX)
  end
  for _, role in ipairs(TAB_ROLES) do
    if role ~= 'guitar.input' then
      local hit = resolved[role]
      if hit then delete_named(hit.track, CHILD_REMOVE) end
    end
  end
end

local function read_tuner()
  local tuner = { freq = 0, cents = 0, level = 0, note = -1, heartbeat = 0 }
  if reaper.gmem_attach then
    reaper.gmem_attach('RappTuner')
    tuner.freq  = reaper.gmem_read(0) or 0
    tuner.cents = reaper.gmem_read(1) or 0
    tuner.level = reaper.gmem_read(2) or 0
    tuner.note  = reaper.gmem_read(3) or -1
    tuner.heartbeat = reaper.gmem_read(4) or 0
  end
  return tuner
end

local function read_scope()
  local scope = { samples = json.array({}), peak = 0, heartbeat = 0 }
  if not reaper.gmem_attach then return scope end
  reaper.gmem_attach('RappScope')
  local n = math.floor(reaper.gmem_read(0) or 0)
  if n > 128 then n = 128 end
  if n < 0 then n = 0 end
  local samples = json.array({})
  for i = 0, n - 1 do
    local v = reaper.gmem_read(10 + i) or 0
    samples[#samples + 1] = math.floor(v * 1000 + 0.5) / 1000
  end
  scope.samples = samples
  scope.peak = reaper.gmem_read(2) or 0
  scope.heartbeat = reaper.gmem_read(3) or 0
  return scope
end

local function track_color(track)
  local c = math.floor(reaper.GetMediaTrackInfo_Value(track, 'I_CUSTOMCOLOR'))
  return c
end

local function peak_db(track)
  -- I_PEAKINFO is dB*10; fall back to -150.
  local v = reaper.Track_GetPeakInfo and reaper.Track_GetPeakInfo(track, 0)
  if v and v > 0 then
    return 20 * math.log(v, 10)
  end
  return -150
end

local function publish_instrument(instrument, resolved)
  local spec = roles.INSTRUMENTS[instrument]
  local tracks = {}
  for _, role in ipairs(roles.owned_by(instrument)) do
    local hit = resolved[role]
    if hit then
      local tr = hit.track
      local fxlist = json.array({})
      for fx = 0, reaper.TrackFX_GetCount(tr) - 1 do
        fxlist[#fxlist + 1] = fx_schema(tr, fx)
      end
      local _, name = reaper.GetSetMediaTrackInfo_String(tr, 'P_NAME', '', false)
      tracks[role] = {
        index = hit.index,
        web_index = hit.index + 1,
        name = name or '',
        tagged = hit.tagged and true or false,
        color = track_color(tr),
        volume = reaper.GetMediaTrackInfo_Value(tr, 'D_VOL'),
        pan = reaper.GetMediaTrackInfo_Value(tr, 'D_PAN'),
        mute = reaper.GetMediaTrackInfo_Value(tr, 'B_MUTE') > 0,
        solo = reaper.GetMediaTrackInfo_Value(tr, 'I_SOLO') > 0,
        recarm = reaper.GetMediaTrackInfo_Value(tr, 'I_RECARM') > 0,
        peak_db = peak_db(tr),
        sends = reaper.GetTrackNumSends(tr, 0),
        fx = fxlist,
      }
    end
  end

  local missing = roles.missing(instrument, resolved)
  local blob = {
    instrument = instrument,
    label = spec.label,
    accent = spec.accent,
    tracks = tracks,
    missing = json.array(missing),
    current_preset = ctx.current_preset[instrument],
    current_bank = ctx.current_bank[instrument],
    current_rig = ctx.current_rig[instrument],
    last_load = ctx.last_load,
    rigs = json.array(chains.list_rigs(fx_chains_dir(), instrument)),
    arming = ctx.arming,
    ramps = ctx.ramps.count,
    tuner = read_tuner(),
    scope = read_scope(),
    warnings = json.array(ctx.warnings),
    agent_uptime = reaper.time_precise() - ctx.started,
  }
  local library = {}
  local currents = ctx.current_chain[instrument] or {}
  for _, role in ipairs(spec.chain) do
    local folder = chains.role_folder(fx_chains_dir(), role)
    local files = json.array({})
    for _, item in ipairs(chains.list_files(folder)) do
      files[#files + 1] = { id = item.id, path = item.path }
    end
    library[role] = {
      folder = folder or '',
      files = files,
      current = currents[role],
    }
  end
  blob.library = library
  set_state('state.' .. instrument, json.encode(blob))
end

----------------------------------------------------------------------
-- commands
----------------------------------------------------------------------

local function owned(instrument, role)
  for _, r in ipairs(roles.owned_by(instrument)) do
    if r == role then return true end
  end
  return false
end

local function apply_preset_cmd(instrument, preset_id, resolved)
  local list, errors = presets.load_all(root_path(), instrument)
  for _, err in ipairs(errors) do ctx.warnings[#ctx.warnings + 1] = err end
  local preset
  for _, p in ipairs(list) do
    if p.id == preset_id then preset = p break end
  end
  if not preset then
    ctx.warnings[#ctx.warnings + 1] = 'unknown preset ' .. tostring(preset_id)
    return
  end
  local banks = presets.load_banks(root_path())
  local bank = preset.bank and banks[preset.bank]
  local resident = true
  if bank then
    resident = presets.residency_diff(bank, resolved)
  end

  if not resident and bank then
    ctx.arming = { preset = preset_id, bank = bank.id, started = reaper.time_precise(), steps = {}, muted = {} }
    local steps = presets.plan_arming(bank, resolved)
    for _, step in ipairs(steps) do
      local hit = resolved[step.role]
      if hit and not step.hideable then
        -- Park blend on the currently audible side so the other slot is free.
        local blend = rata.get(hit.track, step.fx, 'blend') or 0
        local park = blend < 0.5 and 0 or 1
        rata.set(hit.track, step.fx, 'blend', park)
        step.hideable = true
        step.slot = park < 0.5 and 'B' or 'A'
        -- Cover-mute: SetTrackStateChunk may reinstantiate the whole plugin.
        reaper.SetMediaTrackInfo_Value(hit.track, 'B_MUTE', 1)
        ctx.arming.muted[#ctx.arming.muted + 1] = hit.track
      end
      local ok, msg, ms = presets.arm_step(step, resolved)
      ctx.arming.steps[#ctx.arming.steps + 1] = {
        role = step.role, slot = step.slot, ok = ok and true or false,
        msg = msg, ms = ms,
      }
    end
    ctx.arming.settle_until = reaper.time_precise() + rata.LOAD_SETTLE_SECONDS
    ctx.current_bank[instrument] = bank.id
    -- Apply params (including the audible blend crossfade) only after settle.
    ctx.pending_apply = { instrument = instrument, preset = preset }
    return
  end

  local ok, warnings = presets.apply(ctx, preset, resolved)
  for _, w in ipairs(warnings or {}) do ctx.warnings[#ctx.warnings + 1] = w end
  ctx.current_preset[instrument] = preset_id
  if bank then ctx.current_bank[instrument] = bank.id end
end

local function handle_cmd(instrument, raw, resolved)
  if not raw or raw == '' then return end
  local ok, cmd = pcall(json.decode, raw)
  if not ok or type(cmd) ~= 'table' then return end
  local seq = tonumber(cmd.seq) or 0
  if seq ~= 0 and ctx.last_seq[instrument] and seq <= ctx.last_seq[instrument] then
    return
  end
  ctx.last_seq[instrument] = seq
  ctx.warnings = {}

  local op = cmd.op
  if op == 'apply_preset' then
    apply_preset_cmd(instrument, cmd.id, resolved)
  elseif op == 'load_rig' then
    local id = chains.safe_id(cmd.id) or cmd.id
    local root = fx_chains_dir()
    reaper.Undo_BeginBlock()
    reaper.PreventUIRefresh(1)
    local ok, err = pcall(function()
      ctx.last_load = chains.apply_rig(resolved, instrument, root, id)
    end)
    reaper.PreventUIRefresh(-1)
    reaper.TrackList_AdjustWindows(false)
    reaper.Undo_EndBlock('Skeletons: load FX chains', -1)
    if not ok then
      ctx.warnings[#ctx.warnings + 1] = tostring(err)
    else
      ctx.current_chain[instrument] = ctx.current_chain[instrument] or {}
      local spec = roles.INSTRUMENTS[instrument]
      if spec then
        for _, role in ipairs(spec.chain) do
          ctx.current_chain[instrument][role] = id
        end
      end
    end
    ctx.current_rig[instrument] = id
  elseif op == 'load_chain' and owned(instrument, cmd.role) then
    local id = chains.safe_id(cmd.id)
    local path = cmd.path
    if (not path or path == '') and id then
      path = chains.path_for(fx_chains_dir(), cmd.role, id)
    end
    local ok, err, ms = chains.apply_file(resolved, cmd.role, path)
    ctx.last_load = { { role = cmd.role, path = path, ok = ok and true or false, err = err, ms = ms } }
    if ok then
      ctx.current_chain[instrument] = ctx.current_chain[instrument] or {}
      ctx.current_chain[instrument][cmd.role] = id or cmd.id
    elseif err then
      ctx.warnings[#ctx.warnings + 1] = tostring(err)
    end
  elseif op == 'save_chain' and owned(instrument, cmd.role) then
    local id = chains.safe_id(cmd.id)
    local path = cmd.path
    if (not path or path == '') and id then
      path = chains.native_path(fx_chains_dir(), cmd.role, id)
    end
    local ok, err, ms = chains.save_file(resolved, cmd.role, path)
    ctx.last_load = { { role = cmd.role, path = path, ok = ok and true or false, err = err, ms = ms, saved = true } }
    if ok then
      ctx.current_chain[instrument] = ctx.current_chain[instrument] or {}
      ctx.current_chain[instrument][cmd.role] = id or cmd.id
    elseif err then
      ctx.warnings[#ctx.warnings + 1] = tostring(err)
    end
  elseif op == 'save_rig' then
    local id = chains.safe_id(cmd.id)
    local spec = roles.INSTRUMENTS[instrument]
    local results = {}
    if not id then
      ctx.warnings[#ctx.warnings + 1] = 'empty chain name'
    elseif spec then
      reaper.Undo_BeginBlock()
      ctx.current_chain[instrument] = ctx.current_chain[instrument] or {}
      for _, role in ipairs(spec.chain) do
        local path = chains.native_path(fx_chains_dir(), role, id)
        local ok, err, ms = chains.save_file(resolved, role, path)
        results[#results + 1] = { role = role, path = path, ok = ok and true or false, err = err, ms = ms, saved = true }
        if ok then
          ctx.current_chain[instrument][role] = id
        elseif err then
          ctx.warnings[#ctx.warnings + 1] = tostring(err)
        end
      end
      reaper.Undo_EndBlock('Skeletons: save FX chains', -1)
      ctx.current_rig[instrument] = id
    end
    ctx.last_load = results
  elseif op == 'load_fxchain' and owned(instrument, cmd.role) then
    local ok, err, ms = chains.apply_file(resolved, cmd.role, cmd.path)
    ctx.last_load = { { role = cmd.role, ok = ok and true or false, err = err, ms = ms } }
    if not ok and err then ctx.warnings[#ctx.warnings + 1] = tostring(err) end
  elseif op == 'insert_template' then
    local path = cmd.path or (templates_dir() .. '/' .. tostring(cmd.file))
    chains.insert_track_template(path)
  elseif op == 'select' and owned(instrument, cmd.role) then
    local hit = resolved[cmd.role]
    if hit then
      reaper.SetOnlyTrackSelected(hit.track)
      reaper.Main_OnCommand(40913, 0) -- scroll to selected
    end
  elseif op == 'set_vol' and owned(instrument, cmd.role) then
    local hit = resolved[cmd.role]
    if hit and type(cmd.gain) == 'number' then
      reaper.SetMediaTrackInfo_Value(hit.track, 'D_VOL', cmd.gain)
    end
  elseif op == 'set_mute' and owned(instrument, cmd.role) then
    local hit = resolved[cmd.role]
    if hit then
      reaper.SetMediaTrackInfo_Value(hit.track, 'B_MUTE', cmd.value and 1 or 0)
    end
  elseif op == 'set_fx_enabled' and owned(instrument, cmd.role) then
    local hit = resolved[cmd.role]
    if hit and cmd.fx ~= nil then
      reaper.TrackFX_SetEnabled(hit.track, cmd.fx, cmd.value and true or false)
    end
  elseif op == 'set_rata' and owned(instrument, cmd.role) then
    local hit = resolved[cmd.role]
    if hit and cmd.fx ~= nil and cmd.control and type(cmd.value) == 'number' then
      if rata.PINNED[cmd.control] then
        ctx.warnings[#ctx.warnings + 1] = 'refused pinned control ' .. cmd.control
      else
        rata.set(hit.track, cmd.fx, cmd.control, cmd.value)
      end
    end
  elseif op == 'set_param' and owned(instrument, cmd.role) then
    local hit = resolved[cmd.role]
    if hit and cmd.fx ~= nil and cmd.index ~= nil and type(cmd.value) == 'number' then
      reaper.TrackFX_SetParamNormalized(hit.track, cmd.fx, cmd.index, cmd.value)
    end
  elseif op == 'undo' then
    reaper.Main_OnCommand(40029, 0)
  elseif op == 'redo' then
    reaper.Main_OnCommand(40030, 0)
  elseif op == 'ping' then
    -- no-op; publish cycle is enough
  end
end

----------------------------------------------------------------------
-- defer loop
----------------------------------------------------------------------

local pinned = false

local function tick()
  panel.begin_tick()
  local resolved = roles.resolve(0)
  if not pinned then
    for _, hit in pairs(resolved) do
      for fx = 0, reaper.TrackFX_GetCount(hit.track) - 1 do
        if rata.is_ratatouille(hit.track, fx) then
          rata.pin_controls(hit.track, fx)
        end
      end
    end
    pinned = true
  end

  if ctx.arming and ctx.arming.settle_until then
    if reaper.time_precise() >= ctx.arming.settle_until then
      if ctx.pending_apply then
        local pending = ctx.pending_apply
        ctx.pending_apply = nil
        local ok, warnings = presets.apply(ctx, pending.preset, resolved)
        for _, w in ipairs(warnings or {}) do ctx.warnings[#ctx.warnings + 1] = w end
        ctx.current_preset[pending.instrument] = pending.preset.id
      end
      for _, tr in ipairs(ctx.arming.muted or {}) do
        reaper.SetMediaTrackInfo_Value(tr, 'B_MUTE', 0)
      end
      ctx.arming = nil
    end
  end

  ctx.ramps:tick()

  ensure_guitar_utility_fx(resolved)

  for _, instrument in ipairs(roles.ORDER) do
    handle_cmd(instrument, get_state('cmd.' .. instrument), resolved)
    publish_instrument(instrument, resolved)
  end

  set_state('agent.alive', string.format('%.3f', reaper.time_precise()))
  reaper.defer(tick)
end

set_state('agent.root', root_path())
set_state('agent.alive', string.format('%.3f', reaper.time_precise()))
reaper.defer(tick)
