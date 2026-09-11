--[[
  Skeletons Pedal Panel Editor — ReaImGui form that writes schema-1 JSON
  to the Pedal JSFX comment. GTK only reads that comment.

  Actions → Show action list → New action → Load ReaScript → this file.
]]

local function script_dir()
  local src = debug.getinfo(1, 'S').source or ''
  src = src:gsub('^@', '')
  local dir = src:match('^(.*)[/\\]')
  if dir and dir ~= '' then return dir end
  return reaper.GetResourcePath() .. '/Scripts/Skeletons'
end

local DIR = script_dir()
package.path = table.concat({
  DIR .. '/?.lua',
  DIR .. '/skel_lib/?.lua',
  reaper.GetResourcePath() .. '/Scripts/Skeletons/?.lua',
  reaper.GetResourcePath() .. '/Scripts/Skeletons/skel_lib/?.lua',
  package.path,
}, ';')

if not reaper.ImGui_CreateContext then
  reaper.ShowMessageBox(
    'ReaImGui is not installed.\n\n'
      .. 'In ReaPack: ReaTeam Extensions → ReaImGui: ReaScript binding for Dear ImGui.\n'
      .. 'Then restart REAPER and run this action again.',
    'Skeletons Pedal Editor',
    0
  )
  return
end

local json = require('skel_lib.json')
local panel = require('skel_lib.panel')

local ctx = reaper.ImGui_CreateContext('Pedal Panel Editor')
local FIRST = (reaper.ImGui_Cond_FirstUseEver and reaper.ImGui_Cond_FirstUseEver()) or 4
local OPEN = (reaper.ImGui_TreeNodeFlags_DefaultOpen and reaper.ImGui_TreeNodeFlags_DefaultOpen()) or 0

local state = {
  instances = {},
  pick = 0,
  guid = nil,
  doc = panel.default_doc('Pedal'),
  dirty = false,
  status = '',
  err = '',
}

local function track_name(track)
  if not track then return 'Track' end
  local _, name = reaper.GetTrackName(track)
  return name or 'Track'
end

local function list_instances()
  local out = {}
  local ntracks = reaper.CountTracks(0)
  for ti = 0, ntracks - 1 do
    local track = reaper.GetTrack(0, ti)
    local nfx = reaper.TrackFX_GetCount(track)
    for fi = 0, nfx - 1 do
      local _, name = reaper.TrackFX_GetFXName(track, fi, '')
      local ok, ident = reaper.TrackFX_GetNamedConfigParm(track, fi, 'fx_ident')
      if panel.is_pedal(name, ok and ident or '') then
        local guid = reaper.TrackFX_GetFXGUID(track, fi)
        local raw = panel.read_comment(track, fi)
        local wire = panel.parse_wire(raw)
        local title = (wire and wire.title ~= '' and wire.title) or name or 'Pedal'
        out[#out + 1] = {
          track = track,
          fx = fi,
          guid = guid,
          label = track_name(track) .. '  ·  ' .. title,
        }
      end
    end
  end
  return out
end

local function resolve_guid(guid, fresh)
  if not guid then return nil end
  local list = fresh and list_instances() or state.instances
  for _, inst in ipairs(list) do
    if inst.guid == guid then return inst end
  end
  if not fresh then
    for _, inst in ipairs(list_instances()) do
      if inst.guid == guid then return inst end
    end
  end
  return nil
end

local function load_instance(inst)
  if not inst then
    state.doc = panel.default_doc('Pedal')
    state.guid = nil
    state.dirty = false
    state.err = ''
    state.status = ''
    return
  end
  local raw = panel.read_comment(inst.track, inst.fx)
  local doc = panel.parse_wire(raw)
  if not doc then
    local _, name = reaper.TrackFX_GetFXName(inst.track, inst.fx, '')
    doc = panel.default_doc(name)
  end
  panel.fix_indices(doc)
  state.doc = doc
  state.guid = inst.guid
  state.dirty = false
  state.err = ''
  state.status = 'Loaded (not saved until you press Save)'
end

local function hex_to_u32(hex)
  hex = panel.normalize_hex(hex)
  local r, g, b = hex:match('#(%x%x)(%x%x)(%x%x)')
  r, g, b = tonumber(r, 16) or 0, tonumber(g, 16) or 0, tonumber(b, 16) or 0
  return (r << 16) | (g << 8) | b
end

local function u32_to_hex(n)
  -- ColorEdit3 is 0xXXRRGGBB; the high byte is ignored.
  n = math.floor(tonumber(n) or 0) & 0xFFFFFF
  local r = (n >> 16) & 0xFF
  local g = (n >> 8) & 0xFF
  local b = n & 0xFF
  return string.format('#%02x%02x%02x', r, g, b)
end

local function input_text(label, value, flags)
  local rv, text = reaper.ImGui_InputText(ctx, label, value or '', flags or 0)
  return rv, text
end

local function combo_items(insts)
  if #insts == 0 then return '(no Skeletons Pedal on any track)' end
  local parts = {}
  for i, inst in ipairs(insts) do
    parts[i] = inst.label:gsub('%z', ' ')
  end
  return table.concat(parts, '\0') .. '\0'
end

local function count_arr(t, maxn)
  local n = 0
  for i = 1, maxn do
    if not t or t[i] == nil then break end
    n = i
  end
  return n
end

local function draw_ticks(id, ticks)
  ticks = ticks or json.array({})
  json.array(ticks)
  local n = count_arr(ticks, 24)
  reaper.ImGui_Text(ctx, 'Ticks')
  local i = 1
  while i <= n do
    reaper.ImGui_PushID(ctx, id .. 't' .. i)
    local rv, text = input_text('##' .. id .. i, ticks[i])
    if rv then
      ticks[i] = text
      state.dirty = true
    end
    reaper.ImGui_SameLine(ctx)
    if reaper.ImGui_Button(ctx, 'X') then
      for j = i, n - 1 do
        ticks[j] = ticks[j + 1]
      end
      ticks[n] = nil
      n = n - 1
      state.dirty = true
      reaper.ImGui_PopID(ctx)
      -- stay on this index; list shrank
    else
      reaper.ImGui_PopID(ctx)
      i = i + 1
    end
  end
  if reaper.ImGui_Button(ctx, '+ tick##' .. id) then
    ticks[n + 1] = ''
    state.dirty = true
  end
  return ticks
end

local function try_alias(track, fx, index, label)
  -- Cosmetic only. If this named-config key is absent, skip — no chunk rewrite.
  reaper.TrackFX_SetNamedConfigParm(track, fx, 'param.' .. index .. '.alias', label or '')
end

local function mirror_aliases(track, fx, doc)
  local knobs = doc.controls.knobs
  local nk = count_arr(knobs, panel.KNOB_MAX)
  for i = 1, nk do
    local k = knobs[i]
    try_alias(track, fx, k.index, k.label)
  end
  local switches = doc.controls.switches
  local ns = count_arr(switches, panel.SW_MAX)
  for i = 1, ns do
    local s = switches[i]
    try_alias(track, fx, s.index, s.label)
  end
  try_alias(track, fx, 0, doc.wet_label or 'Wet')
  try_alias(track, fx, 1, doc.on_label or 'On')
end

local function save_doc()
  local play = reaper.GetPlayState()
  if play & 4 ~= 0 then
    state.err = 'Cannot save while recording'
    return
  end
  local inst = resolve_guid(state.guid, true)
  if not inst then
    state.err = 'Pedal instance not found (FX moved or deleted)'
    return
  end
  local payload, err = panel.to_json(state.doc)
  if not payload then
    state.err = err or 'invalid document'
    return
  end
  reaper.Undo_BeginBlock()
  local ok = panel.write_comment(inst.track, inst.fx, payload)
  if not ok then
    reaper.Undo_EndBlock('Edit pedal panel (failed)', -1)
    state.err = 'TrackFX_SetNamedConfigParm COMMENT failed'
    return
  end
  reaper.TrackFX_SetNamedConfigParm(inst.track, inst.fx, 'renamed_name', state.doc.title)
  mirror_aliases(inst.track, inst.fx, state.doc)
  reaper.Undo_EndBlock('Edit pedal panel: ' .. state.doc.title, -1)
  state.dirty = false
  state.err = ''
  state.status = 'Saved to FX comment'
  -- Refresh picker labels
  state.instances = list_instances()
end

local function draw_form()
  local doc = state.doc
  doc.controls = doc.controls or { knobs = json.array({}), switches = json.array({}) }
  local knobs = doc.controls.knobs
  local switches = doc.controls.switches
  json.array(knobs)
  json.array(switches)

  local rv, text = input_text('Title', doc.title)
  if rv then
    doc.title = text
    state.dirty = true
  end

  local col = hex_to_u32(doc.color)
  local crv, ncol = reaper.ImGui_ColorEdit3(ctx, 'Color', col)
  if crv then
    doc.color = u32_to_hex(ncol)
    state.dirty = true
  end

  rv, text = input_text('Wet label', doc.wet_label)
  if rv then
    doc.wet_label = text
    state.dirty = true
  end
  rv, text = input_text('On label', doc.on_label)
  if rv then
    doc.on_label = text
    state.dirty = true
  end

  local nk = math.max(2, count_arr(knobs, panel.KNOB_MAX))
  local srv, nknobs = reaper.ImGui_SliderInt(ctx, 'Knob count', nk, 2, panel.KNOB_MAX)
  if srv and nknobs ~= nk then
    panel.set_knob_count(doc, nknobs)
    knobs = doc.controls.knobs
    state.dirty = true
  end
  nk = count_arr(knobs, panel.KNOB_MAX)

  for i = 1, nk do
    local k = knobs[i]
    if reaper.ImGui_CollapsingHeader(ctx, string.format('Knob %d  (param %d)##k', i, k.index), OPEN) then
      rv, text = input_text('Label##k' .. i, k.label)
      if rv then
        k.label = text
        state.dirty = true
      end
      local cur = (k.type == 'discrete') and 1 or 0
      local cv, ni = reaper.ImGui_Combo(ctx, 'Type##k' .. i, cur, 'Continuous\0Discrete\0')
      if cv then
        k.type = (ni == 1) and 'discrete' or 'continuous'
        if k.type == 'discrete' and count_arr(k.ticks, 24) < 2 then
          k.ticks = json.array({ '1', '2' })
        end
        state.dirty = true
      end
      if k.type == 'discrete' then
        k.ticks = draw_ticks('k' .. i, k.ticks)
      end
    end
  end

  local ns = count_arr(switches, panel.SW_MAX)
  srv, ns = reaper.ImGui_SliderInt(ctx, 'Switch count', ns, 0, panel.SW_MAX)
  if srv then
    panel.set_switch_count(doc, ns)
    switches = doc.controls.switches
    state.dirty = true
  end
  ns = count_arr(switches, panel.SW_MAX)

  for i = 1, ns do
    local s = switches[i]
    if reaper.ImGui_CollapsingHeader(ctx, string.format('Switch %d  (param %d)##s', i, s.index), OPEN) then
      rv, text = input_text('Label##s' .. i, s.label)
      if rv then
        s.label = text
        state.dirty = true
      end
      local cur = (s.type == 'multi') and 1 or 0
      local cv, ni = reaper.ImGui_Combo(ctx, 'Type##s' .. i, cur, 'Toggle\0Multi\0')
      if cv then
        s.type = (ni == 1) and 'multi' or 'toggle'
        if s.type == 'multi' and count_arr(s.ticks, 24) < 2 then
          s.ticks = json.array({ 'Off', 'On' })
        end
        state.dirty = true
      end
      if s.type == 'multi' then
        s.ticks = draw_ticks('s' .. i, s.ticks)
      end
    end
  end

  local verr = panel.check(doc)
  local can_save = (verr == nil) and state.guid ~= nil
  if verr then
    reaper.ImGui_TextColored(ctx, 0xFF6666FF, verr)
  end
  if reaper.ImGui_BeginDisabled then
    reaper.ImGui_BeginDisabled(ctx, not can_save)
  end
  if reaper.ImGui_Button(ctx, 'Validate + Save', 200, 32) and can_save then
    save_doc()
  end
  if reaper.ImGui_EndDisabled then
    reaper.ImGui_EndDisabled(ctx)
  end
  if state.err ~= '' then
    reaper.ImGui_TextColored(ctx, 0xFF6666FF, state.err)
  elseif state.status ~= '' then
    reaper.ImGui_TextWrapped(ctx, state.status .. (state.dirty and '  (unsaved edits)' or ''))
  end
end

local function loop()
  state.instances = list_instances()
  if state.guid and not resolve_guid(state.guid) then
    state.status = 'Previous pedal gone; pick another'
    state.guid = nil
  end

  reaper.ImGui_SetNextWindowSize(ctx, 480, 640, FIRST)
  local visible, open = reaper.ImGui_Begin(ctx, 'Pedal Panel Editor', true)
  if visible then
    reaper.ImGui_TextWrapped(ctx, 'Edits stay in this window until Save. GTK reads the FX comment only.')
    reaper.ImGui_Separator(ctx)
    if reaper.ImGui_Button(ctx, 'Refresh list') then
      state.instances = list_instances()
    end
    local labels = combo_items(state.instances)
    local pick = state.pick
    if state.guid then
      for i, inst in ipairs(state.instances) do
        if inst.guid == state.guid then
          pick = i - 1
          break
        end
      end
    end
    local rv, npick = reaper.ImGui_Combo(ctx, 'Pedal instance', pick, labels)
    if rv then
      state.pick = npick
      local inst = state.instances[npick + 1]
      if inst then load_instance(inst) end
    elseif #state.instances > 0 and not state.guid then
      load_instance(state.instances[1])
      state.pick = 0
    end
    reaper.ImGui_Separator(ctx)
    if state.guid then
      draw_form()
    else
      reaper.ImGui_TextWrapped(ctx, 'Add JS: Skeletons Pedal (skel_panel_pedal) to a track, then refresh.')
    end
  end
  reaper.ImGui_End(ctx)
  if open then
    reaper.defer(loop)
  else
    if reaper.ImGui_DestroyContext then
      reaper.ImGui_DestroyContext(ctx)
    end
  end
end

reaper.defer(loop)
