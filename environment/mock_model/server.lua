local cjson = require("cjson")
local socket = require("socket")

local function read_all(path)
    local handle = assert(io.open(path, "r"))
    local content = handle:read("*a")
    handle:close()
    return content
end

local function clamp(value, low, high)
    return math.max(low, math.min(high, value))
end

local function pseudo_unit(text)
    local hash = 17
    for index = 1, #text do
        hash = (hash * 131 + text:byte(index)) % 1000003
    end
    return (hash % 10000) / 10000
end

local profiles = cjson.decode(read_all(assert(arg[1], "profile path required")))
local port = tonumber(arg[2]) or 18080
local server = assert(socket.bind("127.0.0.1", port))
server:settimeout(nil)

local function respond(client, status, payload)
    local body = cjson.encode(payload)
    client:send("HTTP/1.1 " .. status .. "\r\n")
    client:send("Content-Type: application/json\r\n")
    client:send("Content-Length: " .. #body .. "\r\n")
    client:send("Connection: close\r\n\r\n")
    client:send(body)
end

local function process(body)
    local request = cjson.decode(body)
    local profile = profiles[request.item_id]
    if not profile then
        return nil, "unknown item"
    end

    local kind = request.probe_kind or "original"
    local distance = tonumber(request.paraphrase_distance) or 0
    local rarity = tonumber(request.canary_rarity) or 0
    local temperature = tonumber(request.temperature) or 0
    local probability = tonumber(profile.base_accuracy)

    if kind == "paraphrase" then
        probability = probability - distance * tonumber(profile.paraphrase_sensitivity)
    elseif kind == "perturbed" then
        probability = probability - tonumber(profile.perturb_accuracy_drop)
    elseif kind == "order" then
        probability = probability + 0.02
    end
    if request.answer_format == "choice" then
        probability = probability + 0.025
    end
    probability = clamp(probability - 0.20 * temperature, 0.02, 0.99)

    local signature = table.concat({
        tostring(request.item_id),
        tostring(kind),
        tostring(request.seed or 0),
        tostring(distance),
        tostring(rarity),
        tostring(request.framing or "plain"),
        tostring(request.answer_format or "free"),
        tostring(temperature),
        tostring(request.benchmark_age or 0),
    }, "|")
    local correct = pseudo_unit(signature) < probability
    local logprob = tonumber(profile.base_logprob)
    if kind == "paraphrase" then
        logprob = logprob - distance * tonumber(profile.paraphrase_logprob_slope)
    elseif kind == "perturbed" then
        logprob = logprob - tonumber(profile.perturb_logprob_drop)
    end
    logprob = logprob - 0.25 * temperature
    logprob = logprob + math.min((tonumber(request.benchmark_age) or 0) / 600, 0.10)

    local metadata_echo = {}
    if request.framing == "metadata" and profile.metadata_echo then
        metadata_echo = {benchmark_id = request.item_id, split = "heldout"}
    end

    local returned_canary = ""
    if kind == "canary" and rarity >= tonumber(profile.canary_min_rarity) then
        returned_canary = request.canary or ""
    end

    return {
        text = correct and profile.answer or profile.distractor,
        logprob = logprob,
        metadata_echo = metadata_echo,
        returned_canary = returned_canary,
    }
end

while true do
    local client = server:accept()
    client:settimeout(5)
    local request_line = client:receive("*l")
    if request_line then
        local content_length = 0
        while true do
            local line = client:receive("*l")
            if not line or line == "" then
                break
            end
            local value = line:match("^[Cc]ontent%-[Ll]ength:%s*(%d+)")
            if value then
                content_length = tonumber(value)
            end
        end
        local body = content_length > 0 and client:receive(content_length) or ""
        local ok, payload, message = pcall(function()
            local result, err = process(body)
            return result, err
        end)
        if ok and payload then
            respond(client, "200 OK", payload)
        else
            respond(client, "400 Bad Request", {error = message or tostring(payload)})
        end
    end
    client:close()
end
