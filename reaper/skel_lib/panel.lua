--[[
  skel_lib.panel -- schema-1 pedal layout from the FX comment.

  The ReaImGui editor is the only writer. GTK / the agent only read.
  Dummy sliders stay Wet=0, On=1, knobs 2-7, switches 8-10.
]]

local json = require('skel_lib.json')

local panel = {}

panel.KNOB0 = 2
panel.KNOB_MAX = 6
panel.SW0 = 8
panel.SW_MAX = 3
panel.DEFAULT_COLOR = '#2b6f76'

local ALPHA = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
local ALPHA_REV = {}
for i = 1, #ALPHA do
  ALPHA_REV[ALPHA:sub(i, i)] = i - 1
end

function panel.b64decode(data)
  if not data or data == '' then return '' end
  data = data:gsub('[^A-Za-z0-9+/=]', '')
  local out = {}
  for i = 1, #data, 4 do
    local a = ALPHA_REV[data:sub(i, i)] or 0
    local b = ALPHA_REV[data:sub(i + 1, i + 1)] or 0
    local cch, dch = data:sub(i + 2, i + 2), data:sub(i + 3, i + 3)
    local c = (cch ~= '' and cch ~= '=' and ALPHA_REV[cch]) or 0
    local d = (dch ~= '' and dch ~= '=' and ALPHA_REV[dch]) or 0
    local n = a * 262144 + b * 4096 + c * 64 + d
    out[#out + 1] = string.char(math.floor(n / 65536) % 256)
    if cch ~= '=' then
      out[#out + 1] = string.char(math.floor(n / 256) % 256)
    end
    if dch ~= '=' then
      out[#out + 1] = string.char(n % 256)
    end
  end
  return table.concat(out)
end

local function clamp(n, lo, hi)
  n = math.floor(tonumber(n) or lo)
  if n < lo then return lo end
  if n > hi then return hi end
  return n
end

local function as_str(v, fallback)
  if type(v) == 'string' then return v end
  if type(v) == 'number' then return tostring(v) end
  return fallback or ''
end

function panel.normalize_hex(s)
  s = as_str(s, ''):lower():gsub('%s+', '')
  if s:match('^#%x%x%x%x%x%x$') then return s end
  if s:match('^%x%x%x%x%x%x$') then return '#' .. s end
  return panel.DEFAULT_COLOR
end

local function tick_list(raw)
  local steps = json.array({})
  if type(raw) ~= 'table' then return steps end
  local n = 0
  for i = 1, 24 do
    local item = raw[i]
    if item == nil then break end
    local s = as_str(item, ''):gsub('^%s+', ''):gsub('%s+$', '')
    if s ~= '' then
      n = n + 1
      steps[n] = s
    end
  end
  return steps
end

--- Empty ticks are allowed only as a trailing draft row in the editor.
function panel.ticks_have_hole(raw)
  if type(raw) ~= 'table' then return false end
  local saw_empty = false
  for i = 1, 24 do
    if raw[i] == nil then break end
    local s = as_str(raw[i], ''):gsub('^%s+', ''):gsub('%s+$', '')
    if s == '' then
      saw_empty = true
    elseif saw_empty then
      return true
    end
  end
  return false
end

function panel.extract(raw)
  if type(raw) ~= 'string' or raw == '' then return nil end
  local brace = raw:find('{', 1, true)
  if brace then return raw:sub(brace) end
  local best = ''
  for run in raw:gmatch('[A-Za-z0-9%+/=]+') do
    if #run > #best then best = run end
  end
  local bin = panel.b64decode(best ~= '' and best or raw)
  local at = bin:find('{', 1, true)
  if at then return bin:sub(at) end
  return nil
end

local function copy_ticks(src)
  local ticks = json.array({})
  if type(src) ~= 'table' then return ticks end
  local n = 0
  for i = 1, 24 do
    if src[i] == nil then break end
    n = n + 1
    ticks[n] = as_str(src[i], '')
  end
  return ticks
end

function panel.default_doc(title)
  title = as_str(title, ''):gsub('^%s+', ''):gsub('%s+$', '')
  if title == '' then title = 'Pedal' end
  return {
    schema = 1,
    title = title,
    color = panel.DEFAULT_COLOR,
    wet_label = 'Wet',
    on_label = 'On',
    controls = {
      knobs = json.array({
        { index = 2, label = 'Knob 1', type = 'continuous' },
        { index = 3, label = 'Knob 2', type = 'continuous' },
      }),
      switches = json.array({}),
    },
  }
end

local function count_arr(t, maxn)
  if type(t) ~= 'table' then return 0 end
  local n = 0
  for i = 1, maxn do
    if t[i] == nil then break end
    n = i
  end
  return n
end

function panel.fix_indices(doc)
  local knobs = doc.controls and doc.controls.knobs or {}
  local switches = doc.controls and doc.controls.switches or {}
  local nk = clamp(count_arr(knobs, panel.KNOB_MAX), 0, panel.KNOB_MAX)
  if nk < 2 then nk = 2 end
  local ns = clamp(count_arr(switches, panel.SW_MAX), 0, panel.SW_MAX)
  for i = 1, nk do
    knobs[i] = type(knobs[i]) == 'table' and knobs[i] or {}
    knobs[i].index = panel.KNOB0 + i - 1
    knobs[i].label = as_str(knobs[i].label, 'Knob ' .. i)
    local typ = as_str(knobs[i].type, 'continuous')
    knobs[i].type = (typ == 'discrete') and 'discrete' or 'continuous'
    if knobs[i].type == 'discrete' then
      knobs[i].ticks = copy_ticks(knobs[i].ticks)
    else
      knobs[i].ticks = nil
    end
  end
  for i = nk + 1, panel.KNOB_MAX do
    knobs[i] = nil
  end
  for i = 1, ns do
    switches[i] = type(switches[i]) == 'table' and switches[i] or {}
    switches[i].index = panel.SW0 + i - 1
    switches[i].label = as_str(switches[i].label, 'Switch ' .. i)
    local typ = as_str(switches[i].type, 'toggle')
    switches[i].type = (typ == 'multi') and 'multi' or 'toggle'
    if switches[i].type == 'multi' then
      switches[i].ticks = copy_ticks(switches[i].ticks)
    else
      switches[i].ticks = nil
    end
  end
  for i = ns + 1, panel.SW_MAX do
    switches[i] = nil
  end
  json.array(knobs)
  json.array(switches)
  doc.controls = doc.controls or {}
  doc.controls.knobs = knobs
  doc.controls.switches = switches
  return doc
end

function panel.set_knob_count(doc, n)
  n = clamp(n, 2, panel.KNOB_MAX)
  local knobs = doc.controls.knobs
  local have = count_arr(knobs, panel.KNOB_MAX)
  while have < n do
    have = have + 1
    knobs[have] = { index = panel.KNOB0 + have - 1, label = 'Knob ' .. have, type = 'continuous' }
  end
  while have > n do
    knobs[have] = nil
    have = have - 1
  end
  panel.fix_indices(doc)
end

function panel.set_switch_count(doc, n)
  n = clamp(n, 0, panel.SW_MAX)
  local switches = doc.controls.switches
  local have = count_arr(switches, panel.SW_MAX)
  while have < n do
    have = have + 1
    switches[have] = { index = panel.SW0 + have - 1, label = 'Switch ' .. have, type = 'toggle' }
  end
  while have > n do
    switches[have] = nil
    have = have - 1
  end
  panel.fix_indices(doc)
end

--- Non-mutating. Returns an error string, or nil if the document can be saved.
function panel.check(doc)
  if type(doc) ~= 'table' then return 'not a document' end
  if tonumber(doc.schema) ~= 1 then return 'unsupported schema' end
  local title = as_str(doc.title, ''):gsub('^%s+', ''):gsub('%s+$', '')
  if title == '' then return 'title is empty' end
  local controls = type(doc.controls) == 'table' and doc.controls or {}
  local knobs = type(controls.knobs) == 'table' and controls.knobs or {}
  local switches = type(controls.switches) == 'table' and controls.switches or {}
  local nk = count_arr(knobs, panel.KNOB_MAX)
  local ns = count_arr(switches, panel.SW_MAX)
  if nk < 2 or nk > panel.KNOB_MAX then return 'knob count must be 2–6' end
  if ns < 0 or ns > panel.SW_MAX then return 'switch count must be 0–3' end
  for i = 1, nk do
    local k = type(knobs[i]) == 'table' and knobs[i] or {}
    local idx = tonumber(k.index)
    if idx ~= panel.KNOB0 + i - 1 then
      return 'knob index must be ' .. (panel.KNOB0 + i - 1)
    end
    local typ = as_str(k.type, 'continuous')
    local label = as_str(k.label, 'Knob ' .. i)
    if typ == 'discrete' then
      if panel.ticks_have_hole(k.ticks) then
        return 'discrete knob "' .. label .. '" has an empty tick in the middle'
      end
      if #tick_list(k.ticks) < 2 then
        return 'discrete knob "' .. label .. '" needs at least 2 ticks'
      end
    end
  end
  for i = 1, ns do
    local s = type(switches[i]) == 'table' and switches[i] or {}
    local idx = tonumber(s.index)
    if idx ~= panel.SW0 + i - 1 then
      return 'switch index must be ' .. (panel.SW0 + i - 1)
    end
    local typ = as_str(s.type, 'toggle')
    local label = as_str(s.label, 'Switch ' .. i)
    if typ == 'multi' then
      if panel.ticks_have_hole(s.ticks) then
        return 'multi switch "' .. label .. '" has an empty tick in the middle'
      end
      if #tick_list(s.ticks) < 2 then
        return 'multi switch "' .. label .. '" needs at least 2 ticks'
      end
    end
  end
  return nil
end

--- Mutates doc into a save-ready shape. Returns nil, err on failure.
function panel.validate(doc)
  local err = panel.check(doc)
  if err then return nil, err end
  panel.fix_indices(doc)
  local knobs = doc.controls.knobs
  local switches = doc.controls.switches
  local nk = count_arr(knobs, panel.KNOB_MAX)
  local ns = count_arr(switches, panel.SW_MAX)
  for i = 1, nk do
    local k = knobs[i]
    if k.type == 'discrete' then
      k.ticks = tick_list(k.ticks)
    end
  end
  for i = 1, ns do
    local s = switches[i]
    if s.type == 'multi' then
      s.ticks = tick_list(s.ticks)
    end
  end
  doc.title = as_str(doc.title, ''):gsub('^%s+', ''):gsub('%s+$', '')
  doc.color = panel.normalize_hex(doc.color)
  doc.wet_label = as_str(doc.wet_label, 'Wet')
  if doc.wet_label == '' then doc.wet_label = 'Wet' end
  doc.on_label = as_str(doc.on_label, 'On')
  if doc.on_label == '' then doc.on_label = 'On' end
  return doc
end

function panel.to_json(doc)
  local ok, err = panel.validate(doc)
  if not ok then return nil, err end
  -- Rebuild a clean wire table so encode is byte-stable and arrays stay arrays.
  local knobs = json.array({})
  local nk = count_arr(doc.controls.knobs, panel.KNOB_MAX)
  for i = 1, nk do
    local k = doc.controls.knobs[i]
    local item = { index = k.index, label = k.label, type = k.type }
    if k.type == 'discrete' then item.ticks = tick_list(k.ticks) end
    knobs[i] = item
  end
  local switches = json.array({})
  local ns = count_arr(doc.controls.switches, panel.SW_MAX)
  for i = 1, ns do
    local s = doc.controls.switches[i]
    local item = { index = s.index, label = s.label, type = s.type }
    if s.type == 'multi' then item.ticks = tick_list(s.ticks) end
    switches[i] = item
  end
  local wire = {
    schema = 1,
    title = doc.title,
    color = doc.color,
    wet_label = doc.wet_label,
    on_label = doc.on_label,
    controls = {
      knobs = knobs,
      switches = switches,
    },
  }
  return json.encode(wire), nil
end

--- Decode schema-1 JSON (editor working document). Nil if not schema 1.
function panel.parse_wire(text)
  text = panel.extract(type(text) == 'string' and text or '')
  if not text then return nil end
  local ok, doc = pcall(json.decode, text)
  if not ok or type(doc) ~= 'table' then return nil end
  if tonumber(doc.schema) ~= 1 then return nil end
  if as_str(doc.title, '') == '' and type(doc.controls) ~= 'table' then
    return nil
  end
  local controls = type(doc.controls) == 'table' and doc.controls or {}
  local knobs = type(controls.knobs) == 'table' and controls.knobs or json.array({})
  local switches = type(controls.switches) == 'table' and controls.switches or json.array({})
  json.array(knobs)
  json.array(switches)
  doc.controls = { knobs = knobs, switches = switches }
  doc.color = panel.normalize_hex(doc.color)
  doc.wet_label = as_str(doc.wet_label, 'Wet')
  doc.on_label = as_str(doc.on_label, 'On')
  panel.fix_indices(doc)
  return doc
end

--- GTK/agent shape: knobs[].param/type/label/steps, color_hex, wet, on.
function panel.parse(text)
  local doc = panel.parse_wire(text)
  if not doc then return nil end
  local knobs = json.array({})
  local nk = count_arr(doc.controls.knobs, panel.KNOB_MAX)
  for i = 1, nk do
    local k = doc.controls.knobs[i]
    local typ = (k.type == 'discrete') and 'discrete' or 'knob'
    local steps = tick_list(k.ticks)
    if typ == 'discrete' and #steps < 2 then typ = 'knob' end
    knobs[i] = {
      param = k.index,
      type = typ,
      label = as_str(k.label, 'Knob ' .. i),
      steps = steps,
    }
  end
  local switches = json.array({})
  local ns = count_arr(doc.controls.switches, panel.SW_MAX)
  for i = 1, ns do
    local s = doc.controls.switches[i]
    local typ = (s.type == 'multi') and 'multi' or 'toggle'
    local steps = tick_list(s.ticks)
    if typ == 'multi' and #steps < 2 then typ = 'toggle' end
    switches[i] = {
      param = s.index,
      type = typ,
      label = as_str(s.label, 'Switch ' .. i),
      steps = steps,
    }
  end
  return {
    schema = 1,
    title = as_str(doc.title, ''),
    color_hex = panel.normalize_hex(doc.color),
    wet = as_str(doc.wet_label, 'Wet'),
    on = as_str(doc.on_label, 'On'),
    knobs = knobs,
    switches = switches,
  }
end

function panel.is_pedal(name, ident)
  local blob = ((name or '') .. ' ' .. (ident or '')):lower()
  return blob:find('skel_panel_pedal', 1, true) ~= nil
    or blob:find('skeletons pedal', 1, true) ~= nil
    or blob:find('rapp_panel_pedal', 1, true) ~= nil
    or blob:find('reaperapp pedal', 1, true) ~= nil
end

function panel.read_comment(track, fx)
  if not track or not reaper.TrackFX_GetNamedConfigParm then return '' end
  for _, key in ipairs({ 'COMMENT', 'comment', 'fx_comment' }) do
    local ok, val = reaper.TrackFX_GetNamedConfigParm(track, fx, key)
    if ok and type(val) == 'string' and val ~= '' then
      return val
    end
  end
  return ''
end

function panel.write_comment(track, fx, json_str)
  if not track or not reaper.TrackFX_SetNamedConfigParm then return false end
  for _, key in ipairs({ 'COMMENT', 'comment', 'fx_comment' }) do
    local ok = reaper.TrackFX_SetNamedConfigParm(track, fx, key, json_str)
    if ok then return true end
  end
  return false
end

local tick_map = {}
local cache = {}

function panel.begin_tick()
  tick_map = {}
end

function panel.collect(track)
  local memo = tick_map[track]
  if memo then return memo end
  local out = {}
  tick_map[track] = out
  if not track or not reaper.TrackFX_GetCount then return out end
  local n = reaper.TrackFX_GetCount(track)
  for fx = 0, n - 1 do
    local _, name = reaper.TrackFX_GetFXName(track, fx, '')
    local _, ident = reaper.TrackFX_GetNamedConfigParm(track, fx, 'fx_ident')
    if panel.is_pedal(name, ident) then
      local guid = reaper.TrackFX_GetFXGUID(track, fx) or ('slot' .. fx)
      local raw = panel.read_comment(track, fx)
      local prev = cache[guid]
      if prev and prev.hash == raw then
        out[fx] = prev.cfg
      else
        local cfg = panel.parse(raw)
        cache[guid] = { hash = raw, cfg = cfg }
        out[fx] = cfg
      end
    end
  end
  return out
end

function panel.read(track, fx)
  local map = panel.collect(track)
  return map[fx]
end

return panel
