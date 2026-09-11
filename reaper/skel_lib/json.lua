--[[
  skel_lib/json.lua -- minimal JSON encode/decode for REAPER's Lua 5.4.

  REAPER ships no JSON library, and the agent needs to both publish state blobs
  and read preset/bank files from disk. This is deliberately small: it covers the
  subset we generate ourselves plus enough of the spec to read hand-edited files.

  Lua tables are ambiguous between array and object, so encode() decides by
  checking for a contiguous 1..n integer key range. An empty table encodes as {}.
  Use json.array({}) to force [].
]]

local json = {}

-- Marker so an empty or sparse table can still be forced to encode as an array.
local ARRAY_MT = { __jsonarray = true }

function json.array(t)
  return setmetatable(t or {}, ARRAY_MT)
end

function json.is_array(t)
  if getmetatable(t) == ARRAY_MT then return true end
  local n = 0
  for k in pairs(t) do
    if type(k) ~= 'number' or k % 1 ~= 0 or k < 1 then return false end
    n = n + 1
  end
  if n == 0 then return false end -- empty table defaults to object
  for i = 1, n do
    if t[i] == nil then return false end -- sparse, not a clean array
  end
  return true
end

----------------------------------------------------------------------
-- encode
----------------------------------------------------------------------

local ESCAPES = {
  ['"'] = '\\"', ['\\'] = '\\\\', ['\b'] = '\\b', ['\f'] = '\\f',
  ['\n'] = '\\n', ['\r'] = '\\r', ['\t'] = '\\t',
}

local function escape_string(s)
  -- Escape the mandatory set plus all C0 controls, which must be \u-escaped.
  return (s:gsub('[%c"\\]', function(c)
    return ESCAPES[c] or string.format('\\u%04x', c:byte())
  end))
end

local function encode_number(v)
  if v ~= v or v == math.huge or v == -math.huge then
    return 'null' -- JSON has no NaN/Infinity; emit null rather than invalid output
  end
  if math.type(v) == 'integer' then return tostring(v) end
  -- %.17g round-trips a double exactly; trim the common integral case.
  local s = string.format('%.17g', v)
  return s
end

local encode_value

local function encode_table(v, out, depth)
  if depth > 64 then error('json.encode: nesting too deep (cycle?)', 0) end
  if json.is_array(v) then
    out[#out + 1] = '['
    local n = 0
    for k in pairs(v) do
      if type(k) == 'number' and k > n then n = k end
    end
    for i = 1, n do
      if i > 1 then out[#out + 1] = ',' end
      encode_value(v[i], out, depth + 1)
    end
    out[#out + 1] = ']'
  else
    -- Sort keys so output is byte-stable; the app diffs these blobs.
    local keys = {}
    for k in pairs(v) do
      if type(k) == 'string' then keys[#keys + 1] = k end
    end
    table.sort(keys)
    out[#out + 1] = '{'
    for i, k in ipairs(keys) do
      if i > 1 then out[#out + 1] = ',' end
      out[#out + 1] = '"' .. escape_string(k) .. '":'
      encode_value(v[k], out, depth + 1)
    end
    out[#out + 1] = '}'
  end
end

encode_value = function(v, out, depth)
  local t = type(v)
  if v == nil then
    out[#out + 1] = 'null'
  elseif t == 'boolean' then
    out[#out + 1] = v and 'true' or 'false'
  elseif t == 'number' then
    out[#out + 1] = encode_number(v)
  elseif t == 'string' then
    out[#out + 1] = '"' .. escape_string(v) .. '"'
  elseif t == 'table' then
    encode_table(v, out, depth)
  else
    error('json.encode: cannot encode ' .. t, 0)
  end
end

function json.encode(v)
  local out = {}
  encode_value(v, out, 0)
  return table.concat(out)
end

----------------------------------------------------------------------
-- decode
----------------------------------------------------------------------

local function skip_ws(s, i)
  local _, j = s:find('^[ \t\r\n]*', i)
  return (j or i - 1) + 1
end

local decode_value

local function decode_error(s, i, msg)
  local line = 1
  for _ in s:sub(1, i):gmatch('\n') do line = line + 1 end
  error(string.format('json.decode: %s at line %d (offset %d)', msg, line, i), 0)
end

local UNESCAPES = {
  ['"'] = '"', ['\\'] = '\\', ['/'] = '/', b = '\b',
  f = '\f', n = '\n', r = '\r', t = '\t',
}

local function utf8_encode(cp)
  if utf8 and utf8.char then return utf8.char(cp) end
  return '?'
end

local function decode_string(s, i)
  i = i + 1 -- skip opening quote
  local parts = {}
  while true do
    local chunk_start = i
    local c = s:find('["\\]', i)
    if not c then decode_error(s, i, 'unterminated string') end
    if c > chunk_start then parts[#parts + 1] = s:sub(chunk_start, c - 1) end
    local ch = s:sub(c, c)
    if ch == '"' then
      return table.concat(parts), c + 1
    end
    -- backslash escape
    local esc = s:sub(c + 1, c + 1)
    if esc == 'u' then
      local hex = s:sub(c + 2, c + 5)
      if not hex:match('^%x%x%x%x$') then decode_error(s, c, 'bad \\u escape') end
      local cp = tonumber(hex, 16)
      i = c + 6
      -- Combine a surrogate pair if one follows.
      if cp >= 0xD800 and cp <= 0xDBFF and s:sub(i, i + 1) == '\\u' then
        local lo = tonumber(s:sub(i + 2, i + 5), 16)
        if lo and lo >= 0xDC00 and lo <= 0xDFFF then
          cp = 0x10000 + (cp - 0xD800) * 0x400 + (lo - 0xDC00)
          i = i + 6
        end
      end
      parts[#parts + 1] = utf8_encode(cp)
    else
      local lit = UNESCAPES[esc]
      if not lit then decode_error(s, c, 'bad escape \\' .. esc) end
      parts[#parts + 1] = lit
      i = c + 2
    end
  end
end

local function decode_number(s, i)
  local numstr = s:match('^-?%d+%.?%d*[eE]?[-+]?%d*', i)
  if not numstr or numstr == '' then decode_error(s, i, 'bad number') end
  local v = tonumber(numstr)
  if not v then decode_error(s, i, 'bad number ' .. numstr) end
  return v, i + #numstr
end

local function decode_array(s, i)
  local arr = json.array({})
  i = skip_ws(s, i + 1)
  if s:sub(i, i) == ']' then return arr, i + 1 end
  while true do
    local v
    v, i = decode_value(s, i)
    arr[#arr + 1] = v
    i = skip_ws(s, i)
    local ch = s:sub(i, i)
    if ch == ']' then return arr, i + 1 end
    if ch ~= ',' then decode_error(s, i, "expected ',' or ']'") end
    i = skip_ws(s, i + 1)
  end
end

local function decode_object(s, i)
  local obj = {}
  i = skip_ws(s, i + 1)
  if s:sub(i, i) == '}' then return obj, i + 1 end
  while true do
    if s:sub(i, i) ~= '"' then decode_error(s, i, 'expected object key') end
    local k
    k, i = decode_string(s, i)
    i = skip_ws(s, i)
    if s:sub(i, i) ~= ':' then decode_error(s, i, "expected ':'") end
    i = skip_ws(s, i + 1)
    local v
    v, i = decode_value(s, i)
    obj[k] = v
    i = skip_ws(s, i)
    local ch = s:sub(i, i)
    if ch == '}' then return obj, i + 1 end
    if ch ~= ',' then decode_error(s, i, "expected ',' or '}'") end
    i = skip_ws(s, i + 1)
  end
end

decode_value = function(s, i)
  i = skip_ws(s, i)
  local ch = s:sub(i, i)
  if ch == '{' then return decode_object(s, i) end
  if ch == '[' then return decode_array(s, i) end
  if ch == '"' then return decode_string(s, i) end
  if s:sub(i, i + 3) == 'true' then return true, i + 4 end
  if s:sub(i, i + 4) == 'false' then return false, i + 5 end
  if s:sub(i, i + 3) == 'null' then return nil, i + 4 end
  if ch:match('[-%d]') then return decode_number(s, i) end
  decode_error(s, i, 'unexpected character ' .. (ch == '' and '<eof>' or ch))
end

function json.decode(s)
  if type(s) ~= 'string' then error('json.decode: expected string', 0) end
  local v, i = decode_value(s, 1)
  i = skip_ws(s, i)
  if i <= #s then decode_error(s, i, 'trailing content') end
  return v
end

--- Read and decode a file. Returns nil plus a message on failure so callers can
--- surface the problem to the UI instead of raising inside the defer loop.
function json.decode_file(path)
  local f = io.open(path, 'rb')
  if not f then return nil, 'cannot open ' .. path end
  local data = f:read('*a')
  f:close()
  if not data or data == '' then return nil, 'empty file ' .. path end
  local ok, result = pcall(json.decode, data)
  if not ok then return nil, path .. ': ' .. tostring(result) end
  return result
end

function json.encode_file(path, value)
  local ok, encoded = pcall(json.encode, value)
  if not ok then return nil, tostring(encoded) end
  local f = io.open(path, 'wb')
  if not f then return nil, 'cannot write ' .. path end
  f:write(encoded)
  f:close()
  return true
end

return json
