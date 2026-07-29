local M = {}

function M.read_all(path)
    local handle = assert(io.open(path, "r"), "cannot read " .. tostring(path))
    local content = handle:read("*a")
    handle:close()
    return content
end

function M.write_all(path, content)
    local handle = assert(io.open(path, "w"), "cannot write " .. tostring(path))
    assert(handle:write(content))
    handle:close()
end

function M.clamp(value, low, high)
    return math.max(low, math.min(high, value))
end

function M.mean(values)
    assert(#values > 0, "mean of an empty sequence")
    local total = 0
    for _, value in ipairs(values) do
        total = total + value
    end
    return total / #values
end

function M.sorted_keys(source)
    local keys = {}
    for key in pairs(source) do
        keys[#keys + 1] = key
    end
    table.sort(keys)
    return keys
end

-- Twelve significant digits, the same text used for canonical JSON numbers and
-- for the value column of a study probe.
function M.number_text(value)
    return string.format("%.12g", value)
end

function M.shell_quote(value)
    return "'" .. tostring(value):gsub("'", "'\\''") .. "'"
end

return M
