local M = {}

-- The six probe families that carry per item evidence.
M.kinds = {"original", "perturbed", "order", "paraphrase", "metadata", "canary"}

-- The six parameter study axes, in the order they are reported.
M.axes = {
    "paraphrase_distance",
    "canary_rarity",
    "prompt_framing",
    "answer_format",
    "sampling_randomness",
    "benchmark_age",
}

local PERTURBATION = " Counterfactual context replaces one identifying detail."

local function reversed(values)
    local result = {}
    for index = #values, 1, -1 do
        result[#result + 1] = values[index]
    end
    return result
end

local function base(item, kind, seed)
    return {
        item_id = item.id,
        prompt = item.prompt,
        probe_kind = kind,
        answer_format = "free",
        framing = "plain",
        temperature = 0,
        seed = seed,
        option_order = item.options,
        canary = item.canary,
        paraphrase_distance = 0,
        canary_rarity = 0,
        benchmark_age = item.age_months,
    }
end

-- Builds the request body for one probe family. A paraphrase probe needs
-- options.paraphrase, a canary probe needs options.canary_rarity, and anything in
-- options.overrides is applied last.
function M.request(item, kind, seed, options)
    options = options or {}
    local payload = base(item, kind, seed)
    if kind == "perturbed" then
        payload.prompt = item.prompt .. PERTURBATION
    elseif kind == "order" then
        payload.option_order = reversed(item.options)
        payload.answer_format = "choice"
    elseif kind == "paraphrase" then
        local paraphrase = assert(options.paraphrase, "a paraphrase probe needs a paraphrase record")
        payload.prompt = paraphrase.text
        payload.paraphrase_distance = paraphrase.distance
    elseif kind == "metadata" then
        payload.framing = "metadata"
    elseif kind == "canary" then
        payload.canary_rarity = assert(options.canary_rarity, "a canary probe needs a rarity")
    end
    for key, value in pairs(options.overrides or {}) do
        payload[key] = value
    end
    return payload
end

-- Builds the request body for one study point. Returns the payload and the probe
-- family it belongs to.
function M.axis_request(item, axis, value, seed)
    if axis == "paraphrase_distance" then
        local paraphrase = assert(item.paraphrases[1], "the item has no paraphrase")
        return M.request(item, "paraphrase", seed, {
            paraphrase = {text = paraphrase.text, distance = value},
        }), "paraphrase"
    end
    if axis == "canary_rarity" then
        return M.request(item, "canary", seed, {canary_rarity = value}), "canary"
    end
    local field = ({
        prompt_framing = "framing",
        answer_format = "answer_format",
        sampling_randomness = "temperature",
        benchmark_age = "benchmark_age",
    })[axis]
    assert(field, "unknown study axis " .. tostring(axis))
    return M.request(item, "study", seed, {overrides = {[field] = value}}), "study"
end

return M
