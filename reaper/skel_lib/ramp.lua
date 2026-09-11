--[[
  skel_lib/ramp.lua -- time-based parameter ramping driven from the defer loop.

  REAPER does not interpolate FX parameter writes: TrackFX_SetParam takes effect
  at the next audio block, and whether that clicks is entirely up to the plugin.
  Ratatouille's gain and blend ports smooth internally, but the JSFX in the chain
  do not -- sstillwell/1175 and rbj1073 recompute filter coefficients in
  @slider, which is a genuine discontinuity.

  So anything unsmoothed is moved over 20-50 ms in small steps instead of being
  slammed. At the defer loop's ~30 Hz that is only a handful of steps, which is
  enough to turn an audible click into a glide.

  Ramps are keyed, and re-adding a key retargets the existing ramp from wherever
  it currently sits rather than restarting from the old origin. That keeps rapid
  preset changes from stuttering.
]]

local ramp = {}

local Scheduler = {}
Scheduler.__index = Scheduler

function ramp.new()
  return setmetatable({ active = {}, count = 0 }, Scheduler)
end

--- Schedule a ramp.
---   key      unique target id; re-using it retargets in place
---   setter   function(value) applied every tick
---   from     starting value, or nil to continue from the current position
---   to       destination value
---   duration seconds; <= 0 applies immediately
function Scheduler:add(key, setter, from, to, duration)
  if type(setter) ~= 'function' then return end

  local existing = self.active[key]
  local origin = from
  if existing then
    origin = existing.current
  elseif origin == nil then
    origin = to
  end

  if not duration or duration <= 0 or origin == to then
    setter(to)
    if existing then
      self.active[key] = nil
      self.count = self.count - 1
    end
    return
  end

  if not existing then self.count = self.count + 1 end
  self.active[key] = {
    setter = setter,
    from = origin,
    to = to,
    current = origin,
    started = reaper.time_precise(),
    duration = duration,
  }
end

--- Apply one step to every active ramp. Returns how many are still running, so
--- the agent can report "settling" state to the apps.
function Scheduler:tick()
  if self.count == 0 then return 0 end
  local now = reaper.time_precise()

  for key, r in pairs(self.active) do
    local elapsed = now - r.started
    local t = elapsed / r.duration
    if t >= 1 then
      r.current = r.to
      r.setter(r.to)
      self.active[key] = nil
      self.count = self.count - 1
    else
      -- Smoothstep rather than linear: zero velocity at both ends reads as a
      -- deliberate move instead of a sudden stop.
      local eased = t * t * (3 - 2 * t)
      r.current = r.from + (r.to - r.from) * eased
      r.setter(r.current)
    end
  end

  return self.count
end

function Scheduler:cancel(key)
  if self.active[key] then
    self.active[key] = nil
    self.count = self.count - 1
  end
end

function Scheduler:cancel_all()
  self.active = {}
  self.count = 0
end

function Scheduler:busy()
  return self.count > 0
end

return ramp
