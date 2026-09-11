--[[
  reaper/tagger.lua -- stamp P_EXT:skel_role on tracks.

  Safe to re-run. Tagged tracks are left alone; untagged tracks that still have
  the default names from roles.DEFAULT_NAMES get tagged. Pass 'force' as the
  first ExtState command argument to retag even when a different role is present.
]]

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
local installed = reaper.GetResourcePath() .. '/Scripts/Skeletons'
package.path = table.concat({
  SCRIPT_DIR .. '/?.lua',
  SCRIPT_DIR .. '/skel_lib/?.lua',
  installed .. '/?.lua',
  installed .. '/skel_lib/?.lua',
  package.path,
}, ';')

local roles = require('skel_lib.roles')

local force = false
if reaper.HasExtState then
  local arg = reaper.GetExtState('Skeletons', 'tagger.force')
  force = (arg == '1' or arg == 'true')
  reaper.DeleteExtState('Skeletons', 'tagger.force', false)
end

reaper.Undo_BeginBlock()
reaper.PreventUIRefresh(1)

local tagged, skipped, missing = 0, 0, {}
local by_name = {}
for i = 0, reaper.CountTracks(0) - 1 do
  local tr = reaper.GetTrack(0, i)
  local _, name = reaper.GetSetMediaTrackInfo_String(tr, 'P_NAME', '', false)
  if name and name ~= '' and not by_name[name] then
    by_name[name] = tr
  end
end

for role, default_name in pairs(roles.DEFAULT_NAMES) do
  local tr = by_name[default_name]
  if not tr then
    missing[#missing + 1] = role .. ' (' .. default_name .. ')'
  else
    local current = roles.get_tag(tr)
    if current == role then
      skipped = skipped + 1
    elseif current and not force then
      skipped = skipped + 1
    else
      roles.set_tag(tr, role)
      tagged = tagged + 1
    end
  end
end

reaper.PreventUIRefresh(-1)
reaper.TrackList_AdjustWindows(false)
reaper.Undo_EndBlock('Skeletons: tag track roles', -1)

local msg = string.format('Tagged %d, already ok %d, missing %d.', tagged, skipped, #missing)
if #missing > 0 then
  msg = msg .. '\n\nNot found:\n  ' .. table.concat(missing, '\n  ')
end
reaper.ShowMessageBox(msg, 'Skeletons tagger', 0)
