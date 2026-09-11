--[[
  skel_lib/chunk.lua -- surgical RPP / RTrackTemplate chunk parsing.

  Used to read and edit things REAPER exposes no API for -- specifically
  Ratatouille's <STATE> block, which holds the .nam and .wav paths and is not
  parameter-addressable (there is no lv2 named-config-parm; only vst_chunk and
  clap_chunk exist).

  The parser records line spans rather than rebuilding a tree into text, so
  serialising an unedited document returns it byte for byte. Only lines we
  deliberately rewrite change.

  Two format details that bite naive parsers:
    * .RTrackTemplate files use CRLF; .RPP uses LF. Always normalise first.
    * Angle brackets appear mid-line inside data, e.g.
        1919247986<56535472656672726561666972666674> ""
      so block detection must only ever look at the first non-blank character.
]]

local chunk = {}

--- Tags that represent an actual FX instance inside an <FXCHAIN>.
--- Order in the chain is the order these appear.
chunk.FX_TAGS = {
  VST = true, LV2 = true, JS = true, CLAP = true,
  AU = true, DX = true, VIDEO_EFFECT = true, CONTAINER = true,
}

local function normalize(text)
  return (text:gsub('\r\n', '\n'):gsub('\r', '\n'))
end

local function split_lines(text)
  local lines = {}
  for line in (text .. '\n'):gmatch('([^\n]*)\n') do
    lines[#lines + 1] = line
  end
  -- A trailing newline yields one spurious empty element; drop it.
  if #lines > 0 and lines[#lines] == '' then lines[#lines] = nil end
  return lines
end

--- Parse text into { lines = {...}, root = node }.
---
--- node = {
---   tag      = 'LV2' etc, or nil for the synthetic root
---   header   = text following the tag on the opening line
---   first    = index of the '<TAG ...' line (nil for root)
---   last     = index of the matching '>' line (nil for root)
---   children = { node, ... }
--- }
function chunk.parse(text)
  local lines = split_lines(normalize(text))
  local root = { tag = nil, header = '', children = {}, first = nil, last = nil }
  local stack = { root }

  for i = 1, #lines do
    local trimmed = lines[i]:match('^%s*(.-)%s*$')
    local first_char = trimmed:sub(1, 1)

    if first_char == '<' then
      local tag, header = trimmed:match('^<(%S*)%s*(.-)$')
      local node = {
        tag = tag or '',
        header = header or '',
        children = {},
        first = i,
        last = nil,
      }
      local parent = stack[#stack]
      parent.children[#parent.children + 1] = node
      stack[#stack + 1] = node
    elseif trimmed == '>' then
      local node = stack[#stack]
      if #stack > 1 then
        node.last = i
        stack[#stack] = nil
      end
      -- An unbalanced '>' at depth 0 is malformed input; ignore it rather than
      -- throwing, so a slightly odd chunk still yields a usable document.
    end
  end

  return { lines = lines, root = root }
end

function chunk.serialize(doc)
  return table.concat(doc.lines, '\n') .. '\n'
end

function chunk.find_child(node, tag)
  for _, child in ipairs(node.children) do
    if child.tag == tag then return child end
  end
  return nil
end

function chunk.find_children(node, tag)
  local out = {}
  for _, child in ipairs(node.children) do
    if child.tag == tag then out[#out + 1] = child end
  end
  return out
end

--- The single <TRACK> node of a track state chunk.
function chunk.track_node(doc)
  return chunk.find_child(doc.root, 'TRACK')
end

--- Every top-level <TRACK> block, for reading a multi-track .RTrackTemplate.
function chunk.track_nodes(doc)
  return chunk.find_children(doc.root, 'TRACK')
end

--- FX instance nodes of a track, in chain order. The returned index matches the
--- 0-based `fx` argument used by every reaper.TrackFX_* function, so callers can
--- line the two up directly.
function chunk.fx_nodes(track_node)
  local fxchain = track_node and chunk.find_child(track_node, 'FXCHAIN')
  if not fxchain then return {} end
  local out = {}
  for _, child in ipairs(fxchain.children) do
    if chunk.FX_TAGS[child.tag] then
      out[#out + 1] = child
    end
  end
  return out
end

----------------------------------------------------------------------
-- <STATE> access, for LV2 patch properties such as Ratatouille's file slots
----------------------------------------------------------------------

--- RPP tokens may be bare, or wrapped in ", ' or `. Ratatouille writes
--- `S <uri> "/some/path.nam" 3` and the bare word `None` for an empty slot.
local function quote_value(value)
  if value == nil or value == '' then return 'None' end
  if value == 'None' then return 'None' end
  if not value:find('"') then return '"' .. value .. '"' end
  if not value:find("'") then return "'" .. value .. "'" end
  return '`' .. value:gsub('`', '') .. '`'
end

local function unquote_value(token)
  if token == nil then return nil end
  local first = token:sub(1, 1)
  if first == '"' or first == "'" or first == '`' then
    return token:sub(2, -2)
  end
  return token
end

--- Read every `S <uri> <value> <flags>` entry of an FX node's <STATE> block.
--- Returns a uri -> value table; an empty slot reads back as the string 'None'.
function chunk.get_state(fx_node)
  local state = fx_node and chunk.find_child(fx_node, 'STATE')
  if not state then return {} end
  local doc_lines = fx_node.__lines
  local out = {}
  for i = state.first + 1, state.last - 1 do
    local line = doc_lines[i]
    local uri, rest = line:match('^%s*S%s+(%S+)%s+(.*)$')
    if uri then
      local token = rest:match('^(%b"")') or rest:match("^(%b'')")
        or rest:match('^(%S+)')
      out[uri] = unquote_value(token)
    end
  end
  return out
end

--- Rewrite one <STATE> entry in place. Returns true if a line changed.
---
--- Only the single matching line is touched, which is what makes this safe to
--- use on a chain containing large base64 VST payloads.
function chunk.set_state(doc, fx_node, uri, value)
  local state = chunk.find_child(fx_node, 'STATE')
  if not state then return false, 'FX has no <STATE> block' end

  for i = state.first + 1, state.last - 1 do
    local line = doc.lines[i]
    local indent, found_uri, rest = line:match('^(%s*)S%s+(%S+)%s+(.*)$')
    if found_uri == uri then
      -- Preserve the trailing flags field (Ratatouille writes 3).
      local token = rest:match('^(%b"")') or rest:match("^(%b'')")
        or rest:match('^(%S+)') or ''
      local tail = rest:sub(#token + 1)
      local replacement = string.format('%sS %s %s%s',
        indent, uri, quote_value(value), tail)
      if replacement == line then return false end
      doc.lines[i] = replacement
      return true
    end
  end
  return false, 'no <STATE> entry for ' .. uri
end

--- Attach the backing line array to every node, so get_state can read lines
--- without the caller threading `doc` through. Called by chunk.load.
local function attach_lines(node, lines)
  node.__lines = lines
  for _, child in ipairs(node.children) do
    attach_lines(child, lines)
  end
end

function chunk.load(text)
  local doc = chunk.parse(text)
  attach_lines(doc.root, doc.lines)
  return doc
end

--- Read a track's chunk into a parsed document.
function chunk.load_track(track)
  local ok, text = reaper.GetTrackStateChunk(track, '', false)
  if not ok then return nil, 'GetTrackStateChunk failed' end
  return chunk.load(text)
end

function chunk.load_file(path)
  local f = io.open(path, 'rb')
  if not f then return nil, 'cannot open ' .. path end
  local text = f:read('*a')
  f:close()
  return chunk.load(text)
end

----------------------------------------------------------------------
-- misc helpers
----------------------------------------------------------------------

--- Value of a simple `KEY a b c` line directly inside a node.
function chunk.get_field(node, key)
  local lines = node.__lines
  for i = (node.first or 0) + 1, (node.last or #lines) - 1 do
    local line = lines[i]
    local trimmed = line:match('^%s*(.-)%s*$')
    local found, rest = trimmed:match('^(%S+)%s*(.-)$')
    if found == key then return rest end
  end
  return nil
end

--- The FX display name from an FX node's opening line, e.g.
---   <LV2 "LV2: Ratatouille (brummer) (Mono)" urn:brummer:ratatouille ""
--- yields 'LV2: Ratatouille (brummer) (Mono)'.
function chunk.fx_display_name(fx_node)
  local quoted = fx_node.header:match('^%s*(%b"")')
  if quoted then return quoted:sub(2, -2) end
  return fx_node.header:match('^%s*(%S+)') or fx_node.tag
end

--- Replace the <FXCHAIN> of a live track with the contents of an .RfxChain file.
--- The file may be a full <FXCHAIN> wrapper or a bare list of FX instance blocks.
--- Returns ok, err.
function chunk.apply_fxchain_file(track, path, keep_idents)
  local file, err = chunk.load_file(path)
  if not file then return nil, err end

  local incoming
  local fxchain_node = chunk.find_child(file.root, 'FXCHAIN')
  if fxchain_node and fxchain_node.first and fxchain_node.last then
    incoming = {}
    for i = fxchain_node.first, fxchain_node.last do
      incoming[#incoming + 1] = file.lines[i]
    end
  else
    incoming = { '  <FXCHAIN', '    SHOW 0', '    LASTSEL 0', '    DOCKED 0' }
    for _, line in ipairs(file.lines) do
      incoming[#incoming + 1] = line
    end
    incoming[#incoming + 1] = '  >'
  end

  local doc, err2 = chunk.load_track(track)
  if not doc then return nil, err2 end
  local tnode = chunk.track_node(doc)
  if not tnode then return nil, 'no <TRACK> node' end

  local existing = chunk.find_child(tnode, 'FXCHAIN')
  local keep_prefix = {}
  if keep_idents and existing then
    for _, fx_node in ipairs(chunk.fx_nodes(tnode)) do
      local ident = (fx_node.header or '') .. ' ' .. chunk.fx_display_name(fx_node)
      for _, needle in ipairs(keep_idents) do
        if ident:lower():find(needle:lower(), 1, true) then
          for i = fx_node.first, fx_node.last do
            keep_prefix[#keep_prefix + 1] = doc.lines[i]
          end
        end
      end
    end
  end

  -- Build the new chain: kept utility JSFX first, then incoming FX instances.
  local body = {}
  body[#body + 1] = '  <FXCHAIN'
  body[#body + 1] = '    SHOW 0'
  body[#body + 1] = '    LASTSEL 0'
  body[#body + 1] = '    DOCKED 0'
  for _, line in ipairs(keep_prefix) do body[#body + 1] = line end
  local skipping_wrapper = true
  for i, line in ipairs(incoming) do
    local trimmed = line:match('^%s*(.-)%s*$')
    if skipping_wrapper and trimmed:match('^<FXCHAIN') then
      -- skip wrapper header lines until first FX instance
    elseif skipping_wrapper and (trimmed:match('^SHOW') or trimmed:match('^LASTSEL')
        or trimmed:match('^DOCKED') or trimmed:match('^WNDRECT') or trimmed:match('^BYPASS')) then
      -- skip
    else
      skipping_wrapper = false
      if not (i == #incoming and trimmed == '>') then
        body[#body + 1] = line
      end
    end
  end
  body[#body + 1] = '  >'

  local new_lines = {}
  if existing then
    for i = 1, existing.first - 1 do new_lines[#new_lines + 1] = doc.lines[i] end
    for _, line in ipairs(body) do new_lines[#new_lines + 1] = line end
    for i = existing.last + 1, #doc.lines do new_lines[#new_lines + 1] = doc.lines[i] end
  else
    for i = 1, tnode.last - 1 do new_lines[#new_lines + 1] = doc.lines[i] end
    for _, line in ipairs(body) do new_lines[#new_lines + 1] = line end
    for i = tnode.last, #doc.lines do new_lines[#new_lines + 1] = doc.lines[i] end
  end
  doc.lines = new_lines
  local ok = reaper.SetTrackStateChunk(track, chunk.serialize(doc), false)
  if not ok then return nil, 'SetTrackStateChunk rejected FX chain' end
  return true
end

local function ident_matches(fx_node, needles)
  local ident = ((fx_node.header or '') .. ' ' .. chunk.fx_display_name(fx_node)):lower()
  for _, needle in ipairs(needles or {}) do
    if ident:find((needle or ''):lower(), 1, true) then return true end
  end
  return false
end

--- Write hosted FX (not Control / tuner / scope / live) to an .RfxChain file.
function chunk.export_fxchain_file(track, path, skip_needles)
  local doc, err = chunk.load_track(track)
  if not doc then return nil, err end
  local tnode = chunk.track_node(doc)
  if not tnode then return nil, 'no <TRACK> node' end

  local body = { '<FXCHAIN', '  SHOW 0', '  LASTSEL 0', '  DOCKED 0' }
  for _, fx_node in ipairs(chunk.fx_nodes(tnode)) do
    if not ident_matches(fx_node, skip_needles) then
      for i = fx_node.first, fx_node.last do
        body[#body + 1] = doc.lines[i]
      end
    end
  end
  body[#body + 1] = '>'

  local f, werr = io.open(path, 'wb')
  if not f then return nil, werr or ('cannot write ' .. tostring(path)) end
  f:write(table.concat(body, '\n') .. '\n')
  f:close()
  return true
end

return chunk
