local http = require("socket.http")
local ltn12 = require("ltn12")
local json_lines = require("json_lines")

local M = {}

local function validate(response)
    assert(type(response) == "table", "the endpoint must answer with a JSON object")
    assert(type(response.text) == "string", "the endpoint must answer with a text string")
    assert(type(response.logprob) == "number", "the endpoint must answer with a numeric logprob")
    assert(response.logprob == response.logprob, "the endpoint logprob must be finite")
    assert(response.logprob ~= math.huge, "the endpoint logprob must be finite")
    assert(response.logprob ~= -math.huge, "the endpoint logprob must be finite")
    assert(type(response.metadata_echo) == "table", "the endpoint must answer with a metadata_echo object")
    assert(type(response.returned_canary) == "string", "the endpoint must answer with a returned_canary string")
    return response
end

-- Posts one probe payload and returns the validated response body. Any transport
-- failure, non 200 status or malformed body raises.
function M.post(endpoint, payload)
    local body = json_lines.encode(payload)
    local chunks = {}
    local _, status = http.request({
        url = endpoint,
        method = "POST",
        headers = {
            ["content-length"] = tostring(#body),
            ["content-type"] = "application/json",
        },
        source = ltn12.source.string(body),
        sink = ltn12.sink.table(chunks),
    })
    assert(tonumber(status) == 200, "the endpoint returned status " .. tostring(status))
    return validate(json_lines.decode(table.concat(chunks)))
end

local function normalize(text)
    return (text:lower():gsub("^%s+", ""):gsub("%s+$", ""))
end

-- The four measurements every probe row records, read out of one response.
-- A completion counts as correct when it equals the reference answer after case
-- folding and trimming, metadata leaks when the echo object is not empty, and a
-- canary is recalled when the returned token equals the item canary.
function M.measurements(response, item)
    local correct = normalize(response.text) == normalize(item.answer) and 1 or 0
    local metadata_leak = next(response.metadata_echo) ~= nil and 1 or 0
    local canary = item.canary or ""
    local canary_recall = (canary ~= "" and response.returned_canary == canary) and 1 or 0
    return {
        correct = correct,
        logprob = response.logprob,
        metadata_leak = metadata_leak,
        canary_recall = canary_recall,
        completion = response.text,
    }
end

return M
