--[[
  tools/probe.lua -- read-only inspection of the live FX chain.

  Answers the questions the build depends on but that cannot be settled by
  reading REAPER's binary:

    (a) the exact user-preset filename per slot, which confirms whether LV2
        really lands on presets/lv2-urn:brummer:ratatouille.ini and whether a
        JSFX ident containing a slash creates a subdirectory
    (b) fx_ident / fx_type / pdc / nparams per slot, which confirms whether
        Ratatouille's NAM and IR file properties are parameter-addressable
        (they should NOT be -- they live in <STATE>)
    (c) whether the plugin exposes its latency / ms_latency / Xrun output ports
        as readable parameters, which would give the arming path a real
        readiness signal instead of a fixed delay
    (d) the resolved Ratatouille symbol -> parameter index map, so the code can
        stop guessing port order

  This script only reads. It writes nothing to the project and takes no undo
  point. Run it with the guitar tracks present; it inspects role-tagged tracks
  when it finds them and falls back to the selected track otherwise.

  Install: Actions -> Show action list -> New action -> Load ReaScript.
  Output goes to the ReaScript console, and to skel-probe.txt in the resource
  path so the findings can be pasted back into the repo.
]]

local SCRIPT_DIR = ({ reaper.get_action_context() })[2]:match('^(.*)[/\\]')
package.path = SCRIPT_DIR .. '/../reaper/?.lua;' .. SCRIPT_DIR .. '/?.lua;' .. package.path

local ok_roles, roles = pcall(require, 'skel_lib.roles')
local ok_chunk, chunk = pcall(require, 'skel_lib.chunk')
local ok_rata, rata = pcall(require, 'skel_lib.ratatouille')

local out = {}

local function emit(fmt, ...)
  local line = select('#', ...) > 0 and string.format(fmt, ...) or fmt
  out[#out + 1] = line
  reaper.ShowConsoleMsg(line .. '\n')
end

local function ncp(track, fx, name)
  local ok, value = reaper.TrackFX_GetNamedConfigParm(track, fx, name)
  if ok and value ~= '' then return value end
  return '-'
end

local function track_label(track)
  local _, name = reaper.GetSetMediaTrackInfo_String(track, 'P_NAME', '', false)
  local idx = math.floor(reaper.GetMediaTrackInfo_Value(track, 'IP_TRACKNUMBER'))
  return string.format('%d "%s"', idx, name)
end

----------------------------------------------------------------------
-- per-FX report
----------------------------------------------------------------------

local function probe_fx(track, fx)
  local _, disp = reaper.TrackFX_GetFXName(track, fx, '')
  local nparams = reaper.TrackFX_GetNumParams(track, fx)
  local preset_idx, preset_count = reaper.TrackFX_GetPresetIndex(track, fx)
  local _, preset_name = reaper.TrackFX_GetPreset(track, fx, '')
  local preset_file = reaper.TrackFX_GetUserPresetFilename(track, fx)

  emit('  [%d] %s', fx, disp)
  emit('      fx_type=%-8s pdc=%-4s enabled=%s',
    ncp(track, fx, 'fx_type'), ncp(track, fx, 'pdc'),
    tostring(reaper.TrackFX_GetEnabled(track, fx)))
  emit('      fx_ident=%s', ncp(track, fx, 'fx_ident'))
  emit('      presetfile=%s', preset_file ~= '' and preset_file or '(none)')
  emit('      preset=%d/%d cur=%q  nparams=%d',
    preset_idx, preset_count, preset_name or '', nparams)

  -- (b)+(c): dump every parameter. Output-only ports such as Ratatouille's
  -- latency / ms_latency / Xrun would show up here if REAPER exposes them.
  for p = 0, nparams - 1 do
    local _, pname = reaper.TrackFX_GetParamName(track, fx, p, '')
    local value, minv, maxv = reaper.TrackFX_GetParam(track, fx, p)
    local _, formatted = reaper.TrackFX_GetFormattedParamValue(track, fx, p, '')
    local ident = select(2, reaper.TrackFX_GetParamIdent(track, fx, p, '')) or ''
    emit('      p%-3d %-22s %-12s [%s .. %s]  norm=%.4f  ident=%s',
      p, pname or '?', formatted or '', tostring(minv), tostring(maxv),
      reaper.TrackFX_GetParamNormalized(track, fx, p), ident)
  end

  -- (d): the symbol map the rest of the code relies on.
  if ok_rata and rata.is_ratatouille(track, fx) then
    emit('      -- Ratatouille symbol map --')
    local map, method = rata.resolve_params(track, fx)
    emit('      resolved by: %s', method)
    for _, key in ipairs(rata.CONTROL_ORDER) do
      local slot = map[key]
      emit('      %-16s -> %s', key, slot and ('p' .. slot) or 'NOT FOUND')
    end
  end
end

----------------------------------------------------------------------
-- <STATE> report: what is NOT reachable as a parameter
----------------------------------------------------------------------

local function probe_state(track)
  if not ok_chunk then return end
  local doc, err = chunk.load_track(track)
  if not doc then emit('  <chunk read failed: %s>', tostring(err)) return end
  local tnode = chunk.track_node(doc)
  if not tnode then return end
  for i, fx_node in ipairs(chunk.fx_nodes(tnode)) do
    local state = chunk.get_state(fx_node)
    local keys = {}
    for k in pairs(state) do keys[#keys + 1] = k end
    table.sort(keys)
    if #keys > 0 then
      emit('  <STATE> of FX [%d] %s', i - 1, chunk.fx_display_name(fx_node))
      for _, k in ipairs(keys) do
        emit('      %s = %s', k, state[k])
      end
    end
  end
end

----------------------------------------------------------------------
-- main
----------------------------------------------------------------------

local function targets()
  local list = {}
  if ok_roles then
    local resolved = roles.resolve(0)
    for _, instrument in ipairs(roles.ORDER) do
      for _, role in ipairs(roles.owned_by(instrument)) do
        local hit = resolved[role]
        if hit then
          list[#list + 1] = { track = hit.track, role = role, tagged = hit.tagged }
        end
      end
    end
  end
  if #list == 0 then
    -- Nothing tagged or named as expected: fall back to the selection so the
    -- probe is still useful against the raw Cleantonic template.
    for i = 0, reaper.CountSelectedTracks(0) - 1 do
      list[#list + 1] = { track = reaper.GetSelectedTrack(0, i), role = '(selected)' }
    end
  end
  return list
end

reaper.ClearConsole()
emit('Skeletons probe -- read-only')
emit('REAPER %s   resource path: %s', reaper.GetAppVersion(), reaper.GetResourcePath())
emit('libs: roles=%s chunk=%s ratatouille=%s',
  tostring(ok_roles), tostring(ok_chunk), tostring(ok_rata))
emit(string.rep('-', 78))

local list = targets()
if #list == 0 then
  emit('No role-tagged tracks and nothing selected.')
  emit('Select the guitar tracks (or run the skeleton builder) and try again.')
else
  for _, entry in ipairs(list) do
    emit('')
    emit('TRACK %s   role=%s%s', track_label(entry.track), entry.role,
      entry.tagged == false and '  (matched by name, not tagged)' or '')
    local count = reaper.TrackFX_GetCount(entry.track)
    if count == 0 then
      emit('  (no FX)')
    else
      for fx = 0, count - 1 do probe_fx(entry.track, fx) end
    end
    probe_state(entry.track)
  end
end

emit('')
emit(string.rep('-', 78))
emit('Manual checks this script cannot make for you:')
emit('  (c) LV2 preset captures <STATE>?  With a .nam loaded, use Save preset in')
emit('      the FX window, load a different model, then reselect the preset. If')
emit('      the original path returns, REAPER-native LV2 presets carry <STATE>.')
emit('  (d) Arming cost: run tools/probe_timing.lua (it DOES modify state).')

local path = reaper.GetResourcePath() .. '/skel-probe.txt'
local f = io.open(path, 'wb')
if f then
  f:write(table.concat(out, '\n'), '\n')
  f:close()
  emit('')
  emit('Written to %s', path)
end
