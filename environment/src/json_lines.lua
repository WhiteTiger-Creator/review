local cjson = require("cjson")
local util = require("util")

local M = {}

-- Decodes one JSON document and reports a readable failure instead of a raw error.
function M.decode(text)
    local ok, value = pcall(cjson.decode, text)
    assert(ok, "invalid JSON document")
    return value
end

-- Reads every JSON Lines record from the given paths, in the order the paths appear.
function M.read(paths)
    local rows = {}
    for _, path in ipairs(paths) do
        local content = util.read_all(path)
        for line in content:gmatch("[^\n]+") do
            if line:match("%S") then
                rows[#rows + 1] = M.decode(line)
            end
        end
    end
    return rows
end

local function is_array(value)
    local count = 0
    local maximum = 0
    for key in pairs(value) do
        if type(key) ~= "number" or key < 1 or key % 1 ~= 0 then
            return false
        end
        count = count + 1
        maximum = math.max(maximum, key)
    end
    return count > 0 and count == maximum
end

-- Canonical JSON text with sorted object keys and twelve digit numbers, so that
-- two runs over equal values always produce equal bytes.
function M.encode(value)
    local kind = type(value)
    if kind == "nil" then
        return "null"
    end
    if kind == "boolean" then
        return value and "true" or "false"
    end
    if kind == "number" then
        assert(value == value, "cannot encode a non numeric value")
        assert(value ~= math.huge and value ~= -math.huge, "cannot encode an infinite value")
        return util.number_text(value)
    end
    if kind == "string" then
        return cjson.encode(value)
    end
    assert(kind == "table", "cannot encode a " .. kind)
    if is_array(value) then
        local parts = {}
        for index = 1, #value do
            parts[index] = M.encode(value[index])
        end
        return "[" .. table.concat(parts, ",") .. "]"
    end
    local parts = {}
    for index, key in ipairs(util.sorted_keys(value)) do
        assert(type(key) == "string", "object keys must be strings")
        parts[index] = cjson.encode(key) .. ":" .. M.encode(value[key])
    end
    return "{" .. table.concat(parts, ",") .. "}"
end

-- One canonical JSON document per line, newline terminated.
function M.encode_lines(rows)
    local parts = {}
    for index, row in ipairs(rows) do
        parts[index] = M.encode(row)
    end
    if #parts == 0 then
        return ""
    end
    return table.concat(parts, "\n") .. "\n"
end

return M
