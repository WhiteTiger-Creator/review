local M = {}

local TOLERANCE = 1e-12

-- Exhaustive search for the largest subset that satisfies the risk limit, the
-- retention floor and the per modality floor. Ties go to the lower mean upper
-- risk and then to the alphabetically first identifier list.
function M.choose(items, limits)
    local minimum_count = math.ceil(#items * limits.minimum_retention - TOLERANCE)
    local modalities = {}
    for _, item in ipairs(items) do
        modalities[item.modality] = true
    end

    local best_ids, best_mean, best_key = nil, math.huge, nil
    for mask = 0, (1 << #items) - 1 do
        local selected = {}
        local counts = {}
        local upper_total = 0
        for index, item in ipairs(items) do
            if mask & (1 << (index - 1)) ~= 0 then
                selected[#selected + 1] = item.id
                counts[item.modality] = (counts[item.modality] or 0) + 1
                upper_total = upper_total + item.upper
            end
        end
        if #selected >= minimum_count and #selected > 0 then
            local feasible = true
            for modality in pairs(modalities) do
                if (counts[modality] or 0) < limits.minimum_per_modality then
                    feasible = false
                    break
                end
            end
            local upper_mean = upper_total / #selected
            if feasible and upper_mean <= limits.risk_limit + TOLERANCE then
                table.sort(selected)
                local key = table.concat(selected, "\0")
                local better = not best_ids
                    or #selected > #best_ids
                    or (#selected == #best_ids and upper_mean < best_mean - TOLERANCE)
                    or (#selected == #best_ids
                        and math.abs(upper_mean - best_mean) <= TOLERANCE
                        and key < best_key)
                if better then
                    best_ids, best_mean, best_key = selected, upper_mean, key
                end
            end
        end
    end
    assert(best_ids, "no subset satisfies the cleaning limits")
    return best_ids, best_mean
end

return M
