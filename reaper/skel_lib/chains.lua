--[[
  Load and save REAPER-native .RfxChain files onto role-tagged skeleton
  tracks. Chains live in the resource FXChains tree:

    FXChains/<AppFolder>/<TAB>/*.RfxChain
    e.g. FXChains/SkeletonsGuitar/IN/cleantonic.RfxChain

  Utility JSFX (tuner, scope) stay on IN when loading a chain. Control lives
  only on the SkeletonsGuitar folder track and is not kept on tab chains.
]]

local chunk = require('skel_lib.chunk')
local roles = require('skel_lib.roles')

local chains = {}

--- Skip these when exporting a tab chain.
--- Pedal panels (JS: Skeletons Pedal) are part of the board — do not skip them.
chains.SKIP_NEEDLES = {
  'skel_control', 'skeletons control', 'rapp_control', 'reaperapp control',
  'skel_tuner', 'skeletons tuner', 'rapp_tuner', 'reaperapp tuner',
  'skel_scope', 'skeletons scope', 'rapp_scope', 'reaperapp scope',
  'skel_live', 'skeletons live', 'rapp_live', 'reaperapp live',
  'reatune',
}

--- Keep tuner/scope on IN so meters survive a chain load. Do not keep Control
--- on tab tracks — it belongs on guitar.bus.
chains.IN_KEEP = {
  'skel_tuner', 'skeletons tuner', 'rapp_tuner', 'reaperapp tuner',
  'skel_scope', 'skeletons scope', 'rapp_scope', 'reaperapp scope',
}

function chains.keep_needles_for(role)
  if role == 'guitar.input' or (role or ''):match('%.input$') then
    return chains.IN_KEEP
  end
  return {}
end

chains.KEEP_NEEDLES = chains.SKIP_NEEDLES
chains.CONTROL_NEEDLES = chains.SKIP_NEEDLES

--- Older checkout layout: fxchains/<instrument>/<rig>/<this file>
local ROLE_FILE = {
  ['guitar.input']   = 'input.RfxChain',
  ['guitar.pedals']  = 'pedals.RfxChain',
  ['guitar.amp']     = 'amp.RfxChain',
  ['guitar.cabinet'] = 'cabinet.RfxChain',
  ['guitar.fx']      = 'fx.RfxChain',
  ['keys.input']     = 'input.RfxChain',
  ['keys.inst']      = 'inst.RfxChain',
  ['keys.fx']        = 'fx.RfxChain',
  ['mic.input']      = 'input.RfxChain',
  ['mic.fx']         = 'fx.RfxChain',
  ['sidefx.reverb']  = 'reverb.RfxChain',
  ['sidefx.delay']   = 'delay.RfxChain',
}

function chains.role_filename(role)
  return ROLE_FILE[role]
end

function chains.safe_id(name)
  name = tostring(name or '')
  name = name:gsub('%.[Rr][Ff][Xx][Cc]hain$', '')
  name = name:gsub('[^%w%._%-]+', '_')
  name = name:gsub('^_+', ''):gsub('_+$', '')
  if name == '' then return nil end
  return name
end

function chains.role_folder(root, role)
  local inst = roles.instrument_of(role)
  local app = inst and roles.APP_FOLDER[inst]
  local dir = roles.CHAIN_DIR[role]
  if not root or not app or not dir then return nil end
  return root .. '/' .. app .. '/' .. dir
end

function chains.native_path(root, role, id)
  local folder = chains.role_folder(root, role)
  id = chains.safe_id(id)
  if not folder or not id then return nil end
  return folder .. '/' .. id .. '.RfxChain'
end

local function file_exists(path)
  if not path then return false end
  local f = io.open(path, 'rb')
  if not f then return false end
  f:close()
  return true
end

--- Resolve id to a readable .RfxChain: SkeletonsGuitar/<TAB>/<id>.RfxChain first,
--- then the legacy fxchains/<instrument>/<id>/<tab>.RfxChain layout.
function chains.path_for(root, role, id)
  local native = chains.native_path(root, role, id)
  if file_exists(native) then return native end
  local inst = roles.instrument_of(role)
  local fname = ROLE_FILE[role]
  if inst and fname and id then
    local legacy = root .. '/' .. inst .. '/' .. tostring(id) .. '/' .. fname
    if file_exists(legacy) then return legacy end
  end
  return native
end

function chains.ensure_dir(path)
  if not path or path == '' then return nil, 'empty directory' end
  if reaper.RecursiveCreateDirectory then
    reaper.RecursiveCreateDirectory(path, 0)
  end
  return true
end

function chains.list_files(folder)
  local out = {}
  if not folder or folder == '' then return out end
  local i = 0
  while true do
    local fn = reaper.EnumerateFiles(folder, i)
    if not fn then break end
    local id = fn:match('^(.+)%.[Rr][Ff][Xx][Cc]hain$')
    if id then
      out[#out + 1] = { id = id, file = fn, path = folder .. '/' .. fn }
    end
    i = i + 1
  end
  table.sort(out, function(a, b) return a.id < b.id end)
  return out
end

--- Apply one .RfxChain onto the track that owns `role`. Keeps tuner/scope on IN.
function chains.apply_file(resolved, role, path)
  local hit = resolved[role]
  if not hit then return nil, 'no track for role ' .. tostring(role) end
  if not path or path == '' then return nil, 'empty chain path' end
  if not file_exists(path) then return nil, 'missing chain file' end
  local started = reaper.time_precise()
  local ok, err = chunk.apply_fxchain_file(hit.track, path, chains.keep_needles_for(role))
  local ms = (reaper.time_precise() - started) * 1000
  return ok, err, ms
end

function chains.save_file(resolved, role, path)
  local hit = resolved[role]
  if not hit then return nil, 'no track for role ' .. tostring(role) end
  if not path or path == '' then return nil, 'empty chain path' end
  local folder = path:match('^(.*)[/\\][^/\\]+$')
  if folder then chains.ensure_dir(folder) end
  local started = reaper.time_precise()
  local ok, err = chunk.export_fxchain_file(hit.track, path, chains.SKIP_NEEDLES)
  local ms = (reaper.time_precise() - started) * 1000
  return ok, err, ms
end

--- A named rig is one .RfxChain per tab, same stem, under SkeletonsGuitar/IN etc.
function chains.apply_rig(resolved, instrument, root, id)
  local spec = roles.INSTRUMENTS[instrument]
  if not spec then return nil, 'unknown instrument' end
  local results = {}
  for _, role in ipairs(spec.chain) do
    local path = chains.path_for(root, role, id)
    if file_exists(path) then
      local ok, err, ms = chains.apply_file(resolved, role, path)
      results[#results + 1] = { role = role, path = path, ok = ok and true or false, err = err, ms = ms }
    else
      results[#results + 1] = { role = role, path = path, ok = false, err = 'missing chain file' }
    end
  end
  return results
end

--- Insert a track template into the current project. REAPER remaps AUXRECV.
function chains.insert_track_template(path)
  if not path or path == '' then return nil, 'empty template path' end
  reaper.Main_openProject('noprompt:' .. path)
  return true
end

function chains.list_rigs(root, instrument)
  local seen, out = {}, {}
  local function add(name)
    if name and name ~= '' and not seen[name] then
      seen[name] = true
      out[#out + 1] = name
    end
  end
  local spec = roles.INSTRUMENTS[instrument]
  local app = roles.APP_FOLDER[instrument]
  if spec and app then
    for _, role in ipairs(spec.chain) do
      for _, item in ipairs(chains.list_files(chains.role_folder(root, role))) do
        add(item.id)
      end
    end
  end
  -- Legacy checkout layout: <root>/<instrument>/<rig>/
  local legacy = root .. '/' .. tostring(instrument)
  local i = 0
  while true do
    local name = reaper.EnumerateSubdirectories(legacy, i)
    if not name then break end
    add(name)
    i = i + 1
  end
  table.sort(out)
  return out
end

return chains
