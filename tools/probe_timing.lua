--[[
  tools/probe_timing.lua -- measure what a bank change actually costs.

  THIS SCRIPT MODIFIES THE PROJECT. It loads a .nam into a Ratatouille slot and
  times it. Run it with the guitar muted, on a scratch project, and expect one
  undo point.

  It answers the two numbers the arming path is designed around:

    1. How long SetTrackStateChunk takes to rewrite one <STATE> line.
    2. Whether that write RE-INSTANTIATES the plugin. This is the important one.
       Both model slots live in the SAME Ratatouille instance, so if REAPER
       tears the instance down, hiding the load in the blended-away slot does
       not help -- the audible slot dies too, and bank changes must be covered
       by a deliberate mute instead.

  Re-instantiation is detected by writing a sentinel value into an unused
  parameter beforehand and checking whether it survives, and by watching for the
  FX GUID changing.

  Usage: select the track holding Ratatouille, then run.
]]

local SCRIPT_DIR = ({ reaper.get_action_context() })[2]:match('^(.*)[/\\]')
package.path = SCRIPT_DIR .. '/../reaper/?.lua;' .. package.path

local rata  = require('skel_lib.ratatouille')
local chunk = require('skel_lib.chunk')

local out = {}
local function emit(fmt, ...)
  local line = select('#', ...) > 0 and string.format(fmt, ...) or fmt
  out[#out + 1] = line
  reaper.ShowConsoleMsg(line .. '\n')
end

reaper.ClearConsole()
emit('Skeletons timing probe -- THIS MODIFIES THE PROJECT')
emit(string.rep('-', 78))

local track = reaper.GetSelectedTrack(0, 0)
if not track then
  reaper.ShowMessageBox('Select the track holding Ratatouille first.', 'Skeletons', 0)
  return
end

local fx
for i = 0, reaper.TrackFX_GetCount(track) - 1 do
  if rata.is_ratatouille(track, i) then fx = i break end
end
if not fx then
  reaper.ShowMessageBox('No Ratatouille on the selected track.', 'Skeletons', 0)
  return
end

local residency = rata.read_residency(track, fx)
emit('FX slot %d', fx)
emit('  model A = %s', residency.model_a or '(empty)')
emit('  model B = %s', residency.model_b or '(empty)')
emit('  IR A    = %s', residency.ir_a or '(empty)')
emit('  IR B    = %s', residency.ir_b or '(empty)')

-- Pick a model to load: reuse slot A's file if B is empty, which keeps the test
-- self-contained and needs no path from the user.
local candidate = residency.model_b or residency.model_a
if not candidate then
  emit('Both model slots are empty; load one in the plugin UI first.')
  return
end

local target_slot = (rata.away_slot(track, fx)) or 'B'
emit('')
emit('Loading into slot %s (blend = %.3f)', target_slot, rata.get(track, fx, 'blend') or -1)

-- Sentinel: a value we can check for survival. `delay` is unused by our presets
-- and has a wide integer range, so it is safe to borrow for one measurement.
local sentinel = 1234
local delay_before = rata.get(track, fx, 'delay')
rata.set(track, fx, 'delay', sentinel)
local guid_before = reaper.TrackFX_GetFXGUID(track, fx)

reaper.Undo_BeginBlock()
local t0 = reaper.time_precise()
local ok, err = rata.load_slot(track, fx, target_slot, candidate, nil)
local elapsed = (reaper.time_precise() - t0) * 1000
reaper.Undo_EndBlock('Skeletons timing probe', -1)

emit('')
emit('SetTrackStateChunk: %s (%.1f ms)', ok and 'ok' or ('FAILED: ' .. tostring(err)), elapsed)

local guid_after = reaper.TrackFX_GetFXGUID(track, fx)
local delay_after = rata.get(track, fx, 'delay')

emit('FX GUID   before=%s after=%s  %s', tostring(guid_before), tostring(guid_after),
  guid_before == guid_after and 'UNCHANGED' or 'CHANGED')
emit('sentinel  wrote=%d read back=%s  %s', sentinel, tostring(delay_after),
  (delay_after and math.abs(delay_after - sentinel) < 0.5) and 'SURVIVED' or 'LOST')

emit('')
if guid_before == guid_after and delay_after and math.abs(delay_after - sentinel) < 0.5 then
  emit('VERDICT: the instance survived the chunk write.')
  emit('  The arming path can hide a bank change in the blended-away slot.')
  emit('  Set arming.cover_mute = false in the agent config.')
else
  emit('VERDICT: the chunk write re-instantiated the plugin.')
  emit('  Hiding in the away slot is NOT enough -- both slots share one instance.')
  emit('  Keep arming.cover_mute = true so bank changes are a clean short mute.')
end

rata.set(track, fx, 'delay', delay_before or 0)

-- Readiness signal: does REAPER surface Ratatouille's latency output port?
local rp, rname = rata.readiness_source(track, fx)
emit('')
if rp then
  emit('Readiness: parameter p%d (%s) is readable -- poll it instead of a fixed wait.', rp, rname)
else
  emit('Readiness: no latency/ms_latency parameter exposed.')
  emit('  Fall back to rata.LOAD_SETTLE_SECONDS (%.2f s).', rata.LOAD_SETTLE_SECONDS)
end

local path = reaper.GetResourcePath() .. '/skel-probe-timing.txt'
local f = io.open(path, 'wb')
if f then f:write(table.concat(out, '\n'), '\n') f:close()
  emit('')
  emit('Written to %s', path)
end
