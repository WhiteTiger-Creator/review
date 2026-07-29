local linalg = require("linalg")
local panel = require("panel")

local M = {}

local Head = {}
Head.__index = Head

local NORMAL_90 = 1.645

local function logistic(eta)
    return 1 / (1 + math.exp(-eta))
end

local function point_loss(eta, label)
    local shift = math.max(eta, 0)
    return shift - eta * label + math.log(1 + math.exp(-math.abs(eta)))
end

local function centering(rows)
    local width = #panel.features
    local center, spread = {}, {}
    for column = 1, width do
        local total = 0
        for _, row in ipairs(rows) do
            total = total + row.features[column]
        end
        center[column] = total / #rows
        local squared = 0
        for _, row in ipairs(rows) do
            local gap = row.features[column] - center[column]
            squared = squared + gap * gap
        end
        spread[column] = math.sqrt(squared / #rows)
        assert(spread[column] > 0, "a panel column has no spread")
    end
    return center, spread
end

local function standardize(values, center, spread)
    local scaled = {}
    for column = 1, #values do
        scaled[column] = (values[column] - center[column]) / spread[column]
    end
    return scaled
end

local function linear(coefficients, scaled)
    local eta = coefficients[1]
    for column = 1, #scaled do
        eta = eta + coefficients[column + 1] * scaled[column]
    end
    return eta
end

-- Newton fit of the penalized logistic objective, which is the mean negative log
-- likelihood over the used rows plus the penalty times the sum of the squared
-- slopes. The intercept is never penalized.
local function fit(design, labels, penalty, used)
    local width = #design[1] + 1
    local coefficients = {}
    for index = 1, width do
        coefficients[index] = 0
    end
    local total = 0
    for index = 1, #design do
        if used[index] then
            total = total + 1
        end
    end
    assert(total > 0, "a fit needs at least one row")

    for _ = 1, 100 do
        local gradient = {}
        local hessian = {}
        for row = 1, width do
            gradient[row] = 0
            hessian[row] = {}
            for column = 1, width do
                hessian[row][column] = 0
            end
        end
        for index = 1, #design do
            if used[index] then
                local eta = linear(coefficients, design[index])
                local mu = logistic(eta)
                local weight = mu * (1 - mu)
                local residual = mu - labels[index]
                local basis = {1}
                for column = 1, #design[index] do
                    basis[column + 1] = design[index][column]
                end
                for row = 1, width do
                    gradient[row] = gradient[row] + residual * basis[row] / total
                    for column = 1, width do
                        hessian[row][column] = hessian[row][column]
                            + weight * basis[row] * basis[column] / total
                    end
                end
            end
        end
        for row = 2, width do
            gradient[row] = gradient[row] + 2 * penalty * coefficients[row]
            hessian[row][row] = hessian[row][row] + 2 * penalty
        end
        local step = linalg.solve(hessian, gradient)
        local largest = 0
        for index = 1, width do
            coefficients[index] = coefficients[index] - step[index]
            largest = math.max(largest, math.abs(step[index]))
        end
        if largest < 1e-13 then
            break
        end
    end
    return coefficients
end

local function all_rows(count)
    local used = {}
    for index = 1, count do
        used[index] = true
    end
    return used
end

local function held_out_loss(coefficients, design, labels, fold)
    local total = 0
    local count = 0
    for index = 1, #design do
        if fold[index] then
            total = total + point_loss(linear(coefficients, design[index]), labels[index])
            count = count + 1
        end
    end
    assert(count > 0, "an empty fold cannot be scored")
    return total / count
end

-- Leave one modality out sweep. Every penalty is summarized by the mean of the
-- fold losses and by the standard error of those fold values.
local function sweep(rows, design, labels, penalties)
    local folds = panel.modalities(rows)
    local curve = {}
    for _, penalty in ipairs(penalties) do
        local losses = {}
        for _, modality in ipairs(folds) do
            local training, held = {}, {}
            for index, row in ipairs(rows) do
                training[index] = row.modality ~= modality
                held[index] = row.modality == modality
            end
            local coefficients = fit(design, labels, penalty, training)
            losses[#losses + 1] = held_out_loss(coefficients, design, labels, held)
        end
        local mean = 0
        for _, value in ipairs(losses) do
            mean = mean + value
        end
        mean = mean / #losses
        local squared = 0
        for _, value in ipairs(losses) do
            squared = squared + (value - mean) * (value - mean)
        end
        local error_of_mean = math.sqrt(squared / (#losses - 1)) / math.sqrt(#losses)
        curve[#curve + 1] = {penalty = penalty, mean = mean, error = error_of_mean}
    end
    return curve
end

-- The largest penalty whose mean held out loss stays within one standard error
-- of the best mean, with that error measured at the best penalty.
local function one_standard_error(curve)
    local best = curve[1]
    for _, row in ipairs(curve) do
        if row.mean < best.mean then
            best = row
        end
    end
    local limit = best.mean + best.error
    local chosen = best
    for _, row in ipairs(curve) do
        if row.mean <= limit and row.penalty > chosen.penalty then
            chosen = row
        end
    end
    return chosen
end

-- Fits the calibrated head on the adjudicated panel and keeps the leave one out
-- refits that the interval needs.
function M.calibrate(rows, penalties)
    assert(type(penalties) == "table" and #penalties > 0, "a penalty grid is required")
    local center, spread = centering(rows)
    local design, labels = {}, {}
    for index, row in ipairs(rows) do
        design[index] = standardize(row.features, center, spread)
        labels[index] = row.label
    end

    local curve = sweep(rows, design, labels, penalties)
    local chosen = one_standard_error(curve)
    local coefficients = fit(design, labels, chosen.penalty, all_rows(#rows))

    local deleted = {}
    for dropped = 1, #rows do
        local used = all_rows(#rows)
        used[dropped] = false
        deleted[dropped] = fit(design, labels, chosen.penalty, used)
    end

    local slopes = {}
    for index = 2, #coefficients do
        slopes[index - 1] = coefficients[index]
    end
    return setmetatable({
        center = center,
        spread = spread,
        coefficients = coefficients,
        deleted = deleted,
        report = {
            penalty = chosen.penalty,
            mean_log_loss = chosen.mean,
            intercept = coefficients[1],
            coefficients = slopes,
        },
    }, Head)
end

-- The contamination probability of one evidence table with its jackknife
-- interval on the log odds.
function Head:evaluate(evidence)
    local scaled = standardize(panel.vector(evidence), self.center, self.spread)
    local eta = linear(self.coefficients, scaled)
    local count = #self.deleted
    local mean = 0
    local deleted_eta = {}
    for index, coefficients in ipairs(self.deleted) do
        deleted_eta[index] = linear(coefficients, scaled)
        mean = mean + deleted_eta[index]
    end
    mean = mean / count
    local squared = 0
    for _, value in ipairs(deleted_eta) do
        squared = squared + (value - mean) * (value - mean)
    end
    local error_of_eta = math.sqrt((count - 1) / count * squared)
    return logistic(eta),
        logistic(eta - NORMAL_90 * error_of_eta),
        logistic(eta + NORMAL_90 * error_of_eta)
end

return M
