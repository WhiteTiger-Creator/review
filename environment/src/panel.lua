local json_lines = require("json_lines")

local M = {}

-- The nine evidence fields an adjudicated record carries, in the order a
-- coefficient vector reports them.
M.features = {
    "completion_likelihood_gap",
    "exact_match_rate",
    "perturbation_sensitivity",
    "order_invariance",
    "metadata_leak",
    "canary_recall",
    "paraphrase_robustness",
    "substring_overlap",
    "semantic_overlap",
}

-- The feature vector of one evidence table, in M.features order.
function M.vector(evidence)
    local values = {}
    for index, name in ipairs(M.features) do
        local value = evidence[name]
        assert(type(value) == "number", "missing evidence field " .. name)
        values[index] = value
    end
    return values
end

-- Reads the adjudicated panel from the given JSON Lines paths. Every row is
-- returned as a table with id, modality, label and the feature vector, in file
-- order. A row missing a field or carrying a label outside zero and one raises.
function M.load(paths)
    assert(type(paths) == "table" and #paths > 0, "the panel needs at least one path")
    local rows = {}
    for _, record in ipairs(json_lines.read(paths)) do
        assert(type(record.id) == "string", "a panel row needs an id")
        assert(type(record.modality) == "string", "a panel row needs a modality")
        local label = record.contaminated
        assert(label == 0 or label == 1, "a panel label must be zero or one")
        rows[#rows + 1] = {
            id = record.id,
            modality = record.modality,
            label = label,
            features = M.vector(record),
        }
    end
    assert(#rows >= 8, "the adjudicated panel is too small to calibrate")
    return rows
end

-- The distinct modalities of a loaded panel, sorted, which are the folds a
-- leave one modality out sweep runs over.
function M.modalities(rows)
    local seen = {}
    local names = {}
    for _, row in ipairs(rows) do
        if not seen[row.modality] then
            seen[row.modality] = true
            names[#names + 1] = row.modality
        end
    end
    table.sort(names)
    return names
end

return M
