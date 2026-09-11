--[[
  skel_lib/roles.lua -- the track contract shared by every Skeletons launcher.

  Tracks are identified by P_EXT:skel_role, which REAPER stores in the project
  file, keeps invisible in the UI, and preserves across renaming, reordering and
  folder changes. Track indices and names are both too fragile to key on.

  Resolution falls back to an exact name match so the apps work against an
  untagged project too; the tagger then makes the mapping durable.
]]

local roles = {}

roles.EXT_KEY = 'skel_role'
roles.LEGACY_EXT_KEY = 'rapp_role'

--- Signal-chain order per instrument. The Guitar app draws one tab per entry
--- in `chain`, in exactly this order, which is why the list is authoritative
--- rather than derived from project track order.
roles.INSTRUMENTS = {
  guitar = {
    id = 'guitar',
    label = 'Guitar',
    bus = 'guitar.bus',
    chain = { 'guitar.input', 'guitar.pedals', 'guitar.amp', 'guitar.cabinet', 'guitar.fx' },
    accent = '#E8899F', -- Archetype: Tim Henson hot pink
  },
  keys = {
    id = 'keys',
    label = 'Keyboard',
    bus = 'keys.bus',
    chain = { 'keys.input', 'keys.inst', 'keys.fx' },
    accent = '#7FB3E8',
  },
  mic = {
    id = 'mic',
    label = 'Microphone',
    bus = 'mic.bus',
    chain = { 'mic.input', 'mic.fx' },
    accent = '#8FD9A8',
  },
  sidefx = {
    id = 'sidefx',
    label = 'SideFX',
    bus = 'sidefx.bus',
    chain = { 'sidefx.reverb', 'sidefx.delay' },
    accent = '#C9A8E8',
  },
  looper = {
    id = 'looper',
    label = 'Looper',
    bus = nil,
    chain = {},
    accent = '#E8C98F',
  },
}

roles.ORDER = { 'guitar', 'keys', 'mic', 'sidefx', 'looper' }

--- Folder name under TrackTemplates/ and FXChains/.
roles.APP_FOLDER = {
  guitar = 'SkeletonsGuitar',
  keys   = 'SkeletonsKeyboard',
  mic    = 'SkeletonsMicrophone',
  sidefx = 'SkeletonsSideFX',
}

--- Subfolder under FXChains/<App>/ for that tab's .RfxChain files.
roles.CHAIN_DIR = {
  ['guitar.input']   = 'IN',
  ['guitar.pedals']  = 'PEDALS',
  ['guitar.amp']     = 'AMP',
  ['guitar.cabinet'] = 'CAB',
  ['guitar.fx']      = 'FX',
  ['keys.input']     = 'IN',
  ['keys.inst']      = 'INST',
  ['keys.fx']        = 'FX',
  ['mic.input']      = 'IN',
  ['mic.fx']         = 'FX',
  ['sidefx.reverb']  = 'REVERB',
  ['sidefx.delay']   = 'DELAY',
}

--- Default track names, used both by the skeleton builder and by the
--- name-based fallback in resolve(). Keep these in sync with the builder.
roles.DEFAULT_NAMES = {
  ['guitar.bus']     = 'Skeletons Guitar',
  ['guitar.input']   = 'IN',
  ['guitar.pedals']  = 'PEDALS',
  ['guitar.amp']     = 'AMP',
  ['guitar.cabinet'] = 'CAB',
  ['guitar.fx']      = 'FX',

  ['keys.bus']   = 'Skeletons Keyboard',
  ['keys.input'] = 'Keys IN',
  ['keys.inst']  = 'Keys INST',
  ['keys.fx']    = 'Keys FX',

  ['mic.bus']   = 'Skeletons Microphone',
  ['mic.input'] = 'Mic IN',
  ['mic.fx']    = 'Mic FX',

  ['sidefx.bus']    = 'Skeletons SideFX',
  ['sidefx.reverb'] = 'REVERB',
  ['sidefx.delay']  = 'DELAY',
}

--- Older skeleton names still resolve so existing projects keep working.
roles.NAME_ALIASES = {
  ['guitar.bus']     = { 'SkeletonsGuitar', 'GuitarApp', 'Guitar Skeleton' },
  ['guitar.input']   = { 'Input', 'SkeletonsGuitar IN', 'GuitarApp IN' },
  ['guitar.pedals']  = { 'Pre/Pedals' },
  ['guitar.amp']     = { 'Amp' },
  ['guitar.cabinet'] = { 'Cabinet' },
  ['keys.bus']       = { 'SkeletonsKeyboard', 'KeyboardApp', 'Keyboard Skeleton' },
  ['keys.input']     = { 'Keys Input' },
  ['keys.inst']      = { 'Keys Inst' },
  ['keys.fx']        = { 'Keys FX' },
  ['mic.bus']        = { 'SkeletonsMicrophone', 'MicrophoneApp', 'Microphone Skeleton' },
  ['mic.input']      = { 'Mic Input' },
  ['mic.fx']         = { 'Mic FX' },
  ['sidefx.bus']     = { 'SkeletonsSideFX', 'SideFXApp', 'SideFX Bus' },
  ['sidefx.reverb']  = { 'SideFX Reverb' },
  ['sidefx.delay']   = { 'SideFX Delay' },
}

--- Human-facing tab labels, kept short because the tab row is icon-first.
roles.TAB_LABELS = {
  ['guitar.input']   = 'IN',
  ['guitar.pedals']  = 'PEDALS',
  ['guitar.amp']     = 'AMP',
  ['guitar.cabinet'] = 'CAB',
  ['guitar.fx']      = 'FX',
  ['keys.input']     = 'IN',
  ['keys.inst']      = 'INST',
  ['keys.fx']        = 'FX',
  ['mic.input']      = 'IN',
  ['mic.fx']         = 'FX',
  ['sidefx.reverb']  = 'REVERB',
  ['sidefx.delay']   = 'DELAY',
}

--- Every role an instrument owns, bus first. Used for ownership checks: an app
--- may only write to targets inside its own role set, which is what keeps five
--- concurrent apps from fighting over the same parameter.
function roles.owned_by(instrument)
  local spec = roles.INSTRUMENTS[instrument]
  if not spec then return {} end
  local out = {}
  if spec.bus then out[#out + 1] = spec.bus end
  for _, r in ipairs(spec.chain) do out[#out + 1] = r end
  return out
end

function roles.instrument_of(role)
  return role and role:match('^([^.]+)%.') or nil
end

----------------------------------------------------------------------
-- tagging and resolution
----------------------------------------------------------------------

function roles.get_tag(track)
  local ok, value = reaper.GetSetMediaTrackInfo_String(
    track, 'P_EXT:' .. roles.EXT_KEY, '', false)
  if ok and value ~= '' then return value end
  ok, value = reaper.GetSetMediaTrackInfo_String(
    track, 'P_EXT:' .. roles.LEGACY_EXT_KEY, '', false)
  if ok and value ~= '' then return value end
  return nil
end

function roles.set_tag(track, role)
  return reaper.GetSetMediaTrackInfo_String(
    track, 'P_EXT:' .. roles.EXT_KEY, role or '', true)
end

local function track_name(track)
  local _, name = reaper.GetSetMediaTrackInfo_String(track, 'P_NAME', '', false)
  return name or ''
end

--- Build role -> { track, index, name, tagged } for the current project.
---
--- Two passes on purpose: every explicit P_EXT tag wins before any name guess
--- is considered, so a tagged project is never overridden by a coincidental
--- name match elsewhere.
function roles.resolve(proj)
  proj = proj or 0
  local map, by_name = {}, {}

  local count = reaper.CountTracks(proj)
  for i = 0, count - 1 do
    local tr = reaper.GetTrack(proj, i)
    local tag = roles.get_tag(tr)
    if tag and not map[tag] then
      map[tag] = { track = tr, index = i, name = track_name(tr), tagged = true }
    end
    local nm = track_name(tr)
    if nm ~= '' and not by_name[nm] then
      by_name[nm] = { track = tr, index = i, name = nm }
    end
  end

  for role, default_name in pairs(roles.DEFAULT_NAMES) do
    if not map[role] then
      local hit = by_name[default_name]
      if hit then
        map[role] = { track = hit.track, index = hit.index, name = hit.name, tagged = false }
      end
    end
  end
  for role, aliases in pairs(roles.NAME_ALIASES or {}) do
    if not map[role] then
      for _, alias in ipairs(aliases) do
        local hit = by_name[alias]
        if hit then
          map[role] = { track = hit.track, index = hit.index, name = hit.name, tagged = false }
          break
        end
      end
    end
  end

  return map
end

--- Which roles an instrument expects but cannot find. The apps render these as
--- dimmed tabs with a create affordance rather than silently omitting them.
function roles.missing(instrument, resolved)
  local out = {}
  for _, role in ipairs(roles.owned_by(instrument)) do
    if not resolved[role] then out[#out + 1] = role end
  end
  return out
end

return roles
