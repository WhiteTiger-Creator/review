local cleaning = require("cleaning")
local http_probe = require("http_probe")
local json_lines = require("json_lines")
local overlap = require("overlap")
local panel = require("panel")
local scoring = require("scoring")
local store = require("store")
local util = require("util")
local variants = require("variants")

local M = {}

local STAGING = "/app/output/.memscope-staging"

local function ensure_configuration(config)
    assert(type(config) == "table", "the configuration must be an object")
    assert(type(config.endpoint) == "string", "the configuration needs an endpoint")
    assert(type(config.benchmark_paths) == "table" and #config.benchmark_paths > 0, "benchmark paths are required")
    assert(type(config.corpus_paths) == "table" and #config.corpus_paths > 0, "corpus paths are required")
    assert(type(config.embedding_paths) == "table" and #config.embedding_paths > 0, "embedding paths are required")
    assert(type(config.output) == "table", "output paths are required")
    assert(type(config.output.audit) == "string", "an audit output path is required")
    assert(type(config.output.database) == "string", "a database output path is required")
    assert(type(config.output.cleaned) == "string", "a cleaned output path is required")
    assert(type(config.seeds) == "table" and #config.seeds >= 3, "at least three seeds are required")
    assert(type(config.study) == "table", "study axes are required")
    for _, axis in ipairs(variants.axes) do
        assert(type(config.study[axis]) == "table" and #config.study[axis] > 0, "missing study axis " .. axis)
    end
    assert(type(config.calibration) == "table", "a calibration block is required")
    assert(
        type(config.calibration.panel_paths) == "table" and #config.calibration.panel_paths > 0,
        "adjudicated panel paths are required"
    )
    assert(
        type(config.calibration.penalties) == "table" and #config.calibration.penalties > 0,
        "a penalty grid is required"
    )
    for _, penalty in ipairs(config.calibration.penalties) do
        assert(type(penalty) == "number" and penalty > 0, "a penalty must be a positive number")
    end
    assert(type(config.cleaning) == "table", "cleaning limits are required")
    assert(type(config.cleaning.risk_limit) == "number", "a risk limit is required")
    assert(type(config.cleaning.minimum_retention) == "number", "a retention floor is required")
    assert(type(config.cleaning.minimum_per_modality) == "number", "a modality floor is required")
end

local function collect_evidence(item, config, database)
    local kept = {}
    local function issue(kind, seed, options)
        local payload = variants.request(item, kind, seed, options)
        local measured = http_probe.measurements(http_probe.post(config.endpoint, payload), item)
        database:add_probe({
            item_id = item.id,
            kind = kind,
            axis = "",
            seed = seed,
            correct = measured.correct,
            logprob = measured.logprob,
            metadata_leak = measured.metadata_leak,
            canary_recall = measured.canary_recall,
            completion = measured.completion,
        })
        return measured
    end

    local original, perturbed, order = {}, {}, {}
    local original_logprob = {}
    for _, seed in ipairs(config.seeds) do
        local row = issue("original", seed)
        original[#original + 1] = row.correct
        original_logprob[#original_logprob + 1] = row.logprob
        perturbed[#perturbed + 1] = issue("perturbed", seed).correct
        order[#order + 1] = issue("order", seed).correct
    end

    local paraphrase, paraphrase_logprob = {}, {}
    for index, record in ipairs(item.paraphrases) do
        local seed = config.seeds[((index - 1) % #config.seeds) + 1]
        local row = issue("paraphrase", seed, {paraphrase = record})
        paraphrase[#paraphrase + 1] = row.correct
        paraphrase_logprob[#paraphrase_logprob + 1] = row.logprob
    end

    local rarity = config.study.canary_rarity[#config.study.canary_rarity]
    local metadata, canary = {}, {}
    for index = 1, 2 do
        local seed = config.seeds[index]
        metadata[#metadata + 1] = issue("metadata", seed).metadata_leak
        canary[#canary + 1] = issue("canary", seed, {canary_rarity = rarity}).canary_recall
    end

    kept.exact_match_rate = util.mean(original)
    kept.paraphrase_robustness = util.mean(paraphrase)
    kept.completion_likelihood_gap = util.mean(original_logprob) - util.mean(paraphrase_logprob)
    kept.perturbation_sensitivity = math.max(0, kept.exact_match_rate - util.mean(perturbed))
    kept.order_invariance = util.mean(order)
    kept.metadata_leak = util.mean(metadata)
    kept.canary_recall = util.mean(canary)
    return kept
end

local function run_study(benchmarks, config, database)
    local rows = {}
    for _, axis in ipairs(variants.axes) do
        for _, value in ipairs(config.study[axis]) do
            local signals = {}
            for _, item in ipairs(benchmarks) do
                local payload, kind = variants.axis_request(item, axis, value, config.seeds[1])
                local measured = http_probe.measurements(http_probe.post(config.endpoint, payload), item)
                database:add_probe({
                    item_id = item.id,
                    kind = kind,
                    axis = axis,
                    value = value,
                    seed = config.seeds[1],
                    correct = measured.correct,
                    logprob = measured.logprob,
                    metadata_leak = measured.metadata_leak,
                    canary_recall = measured.canary_recall,
                    completion = measured.completion,
                })
                if axis == "paraphrase_distance" or axis == "benchmark_age" then
                    signals[#signals + 1] = measured.logprob
                elseif axis == "canary_rarity" then
                    signals[#signals + 1] = measured.canary_recall
                elseif axis == "prompt_framing" then
                    signals[#signals + 1] = measured.metadata_leak
                else
                    signals[#signals + 1] = measured.correct
                end
            end
            rows[#rows + 1] = {axis = axis, value = value, mean_signal = util.mean(signals)}
        end
    end
    return rows
end

function M.run(config_path)
    local config = json_lines.decode(util.read_all(config_path))
    ensure_configuration(config)

    local benchmarks = json_lines.read(config.benchmark_paths)
    local corpus = json_lines.read(config.corpus_paths)
    local corpus_embeddings = json_lines.read(config.embedding_paths)
    assert(#benchmarks >= 4, "the benchmark is too small to audit")
    table.sort(benchmarks, function(left, right)
        return left.id < right.id
    end)

    local adjudicated = panel.load(config.calibration.panel_paths)
    local head = scoring.calibrate(adjudicated, config.calibration.penalties)

    local database = store.new()
    local items = {}
    for _, item in ipairs(benchmarks) do
        local evidence = collect_evidence(item, config, database)
        evidence.substring_overlap = overlap.substring(item.prompt, corpus)
        evidence.semantic_overlap = overlap.semantic(item.embedding, corpus_embeddings)
        local score, lower, upper = head:evaluate(evidence)
        items[#items + 1] = {
            id = item.id,
            modality = item.modality,
            completion_likelihood_gap = evidence.completion_likelihood_gap,
            exact_match_rate = evidence.exact_match_rate,
            perturbation_sensitivity = evidence.perturbation_sensitivity,
            order_invariance = evidence.order_invariance,
            metadata_leak = evidence.metadata_leak,
            canary_recall = evidence.canary_recall,
            paraphrase_robustness = evidence.paraphrase_robustness,
            substring_overlap = evidence.substring_overlap,
            semantic_overlap = evidence.semantic_overlap,
            score = score,
            lower = lower,
            upper = upper,
        }
    end

    local study_rows = run_study(benchmarks, config, database)

    local retained, mean_upper = cleaning.choose(items, config.cleaning)
    local retained_set = {}
    for _, id in ipairs(retained) do
        retained_set[id] = true
    end
    local removed = {}
    for _, item in ipairs(items) do
        item.decision = retained_set[item.id] and "keep" or "remove"
        if not retained_set[item.id] then
            removed[#removed + 1] = item.id
        end
    end
    table.sort(removed)

    for _, item in ipairs(items) do
        database:add_item(item)
    end
    for _, row in ipairs(study_rows) do
        database:add_study(row)
    end

    local audit = {
        items = items,
        calibration = head.report,
        summary = {item_count = #items, probe_count = database:probe_count()},
        parameter_study = study_rows,
        cleaning = {
            retained_ids = retained,
            removed_ids = removed,
            retained_fraction = #retained / #items,
            mean_upper_risk = mean_upper,
        },
    }

    local by_id = {}
    for _, item in ipairs(benchmarks) do
        by_id[item.id] = item
    end
    local cleaned = {}
    for _, id in ipairs(retained) do
        cleaned[#cleaned + 1] = by_id[id]
    end

    os.execute("rm -rf " .. util.shell_quote(STAGING))
    assert(os.execute("mkdir -p " .. util.shell_quote(STAGING)))
    util.write_all(STAGING .. "/audit.json", json_lines.encode(audit) .. "\n")
    util.write_all(STAGING .. "/cleaned.jsonl", json_lines.encode_lines(cleaned))
    database:write(STAGING .. "/probes.sqlite")

    assert(os.rename(STAGING .. "/audit.json", config.output.audit))
    assert(os.rename(STAGING .. "/probes.sqlite", config.output.database))
    assert(os.rename(STAGING .. "/cleaned.jsonl", config.output.cleaned))
    os.execute("rm -rf " .. util.shell_quote(STAGING))
end

return M
