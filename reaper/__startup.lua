--[[
  Drop this file at ~/.config/REAPER/Scripts/__startup.lua
  (or append the dofile line if you already have a startup script).
]]

local resource = reaper.GetResourcePath()
local candidates = {
  resource .. '/Scripts/Skeletons/skel_agent.lua',
  resource .. '/Scripts/ReaperAPP/rapp_agent.lua',
}

-- Also honour a workspace checkout via ExtState.
local root = reaper.GetExtState('Skeletons', 'root')
if root == '' then
  root = reaper.GetExtState('ReaperAPP', 'root')
end
if root ~= '' then
  candidates[#candidates + 1] = root .. '/reaper/skel_agent.lua'
  candidates[#candidates + 1] = root .. '/reaper/rapp_agent.lua'
end

for _, path in ipairs(candidates) do
  local f = io.open(path, 'rb')
  if f then
    f:close()
    dofile(path)
    return
  end
end
