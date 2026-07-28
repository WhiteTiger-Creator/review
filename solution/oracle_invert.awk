BEGIN {
    FS = "\t"
    OFS = "\t"
    lambda14 = log(2) / 5730
    holdout_active = 0
    holdout_label = 0
}

FNR == 1 { next }

ARGIND == 1 {
    plot = $1
    i = ++layer_count[plot]
    plots[plot] = 1
    depth[plot, i] = $2 + 0
    temp[plot, i] = $3 + 0
    moisture[plot, i] = $4 + 0
    clay[plot, i] = $5 + 0
    carbon_input[plot, i] = $6 + 0
    input_f14c[plot, i] = $7 + 0
    next
}

ARGIND == 2 {
    forcing_seen[$1]++
    moisture_scale[$1] = $2 + 0
    oxygen_scale[$1] = $3 + 0
    next
}

ARGIND == 3 {
    key = $1 SUBSEP depth_key($2)
    observation_seen[key]++
    observed_carbon[key] = $3 + 0
    observed_respiration[key] = $4 + 0
    observed_f14c[key] = $5 + 0
    sigma_carbon[key] = $6 + 0
    sigma_respiration[key] = $7 + 0
    sigma_f14c[key] = $8 + 0
    observed_fold[key] = $9 + 0
    fold_present[$9 + 0] = 1
    observation_count[$1]++
    next
}

ARGIND == 4 {
    bound_seen[$1]++
    lower_bound[$1] = $2 + 0
    upper_bound[$1] = $3 + 0
    next
}

ARGIND == 5 {
    weight_seen[$1 + 0]++
    if (weight_seen[$1 + 0] == 1) {
        candidate_weight[++weight_count] = $1 + 0
    }
    next
}

function depth_key(value) {
    return sprintf("%.12g", value + 0)
}

function fail(message) {
    print "soilfit: " message > "/dev/stderr"
    exit 2
}

function clip(value, low, high) {
    if (value < low) {
        return low
    }
    if (value > high) {
        return high
    }
    return value
}

function abs(value) {
    return value < 0 ? -value : value
}

function sql_text(value, quoted) {
    quoted = value
    gsub(/'/, "''", quoted)
    return "'" quoted "'"
}

function ascending(values, count, i, j, swap) {
    for (i = 2; i <= count; i++) {
        swap = values[i]
        j = i - 1
        while (j >= 1 && values[j] > swap) {
            values[j + 1] = values[j]
            j--
        }
        values[j + 1] = swap
    }
}

function trains(plot, i, key) {
    if (!holdout_active) {
        return 1
    }
    key = plot SUBSEP depth_key(depth[plot, i])
    return observed_fold[key] != holdout_label
}

function solve_rhs(plot, k0, mixing, shift, rhs, answer,
                   n, i, neighbors, denominator, lower, diagonal,
                   upper, modified_upper, modified_rhs) {
    delete answer
    delete lower
    delete diagonal
    delete upper
    delete modified_upper
    delete modified_rhs
    n = layer_count[plot]
    for (i = 1; i <= n; i++) {
        decay[plot, i] = k0 * exp(0.069314718 * (temp[plot, i] - 10)) \
            * moisture[plot, i] * moisture_scale[plot] * oxygen_scale[plot] \
            * (1 - 0.35 * clay[plot, i])
        neighbors = (i > 1) + (i < n)
        lower[i] = (i > 1) ? -mixing : 0
        diagonal[i] = decay[plot, i] + neighbors * mixing + shift
        upper[i] = (i < n) ? -mixing : 0
        if (diagonal[i] <= 0) {
            fail("singular profile system")
        }
    }
    denominator = diagonal[1]
    if (abs(denominator) < 1e-14) {
        fail("singular profile system")
    }
    modified_upper[1] = upper[1] / denominator
    modified_rhs[1] = rhs[1] / denominator
    for (i = 2; i <= n; i++) {
        denominator = diagonal[i] - lower[i] * modified_upper[i - 1]
        if (abs(denominator) < 1e-14) {
            fail("singular profile system")
        }
        modified_upper[i] = (i < n) ? upper[i] / denominator : 0
        modified_rhs[i] = (rhs[i] - lower[i] * modified_rhs[i - 1]) / denominator
    }
    answer[n] = modified_rhs[n]
    for (i = n - 1; i >= 1; i--) {
        answer[i] = modified_rhs[i] - modified_upper[i] * answer[i + 1]
    }
}

function unit_profile(plot, k0, cue, mixing, carbon, respiration, isotope,
                      i, n, rhs) {
    n = layer_count[plot]
    delete rhs
    for (i = 1; i <= n; i++) {
        rhs[i] = carbon_input[plot, i]
    }
    solve_rhs(plot, k0, mixing, 0, rhs, carbon)
    for (i = 1; i <= n; i++) {
        respiration[i] = (1 - cue) * decay[plot, i] * carbon[i]
        rhs[i] = carbon_input[plot, i] * input_f14c[plot, i]
    }
    solve_rhs(plot, k0, mixing, lambda14, rhs, isotope)
}

function effect_of(plot, carbon, respiration,
                   i, n, key, numerator, denominator) {
    n = layer_count[plot]
    numerator = active_weight
    denominator = active_weight
    for (i = 1; i <= n; i++) {
        if (!trains(plot, i)) {
            continue
        }
        key = plot SUBSEP depth_key(depth[plot, i])
        numerator += carbon[i] * observed_carbon[key] / (sigma_carbon[key] ^ 2)
        numerator += respiration[i] * observed_respiration[key] / (sigma_respiration[key] ^ 2)
        denominator += carbon[i] ^ 2 / (sigma_carbon[key] ^ 2)
        denominator += respiration[i] ^ 2 / (sigma_respiration[key] ^ 2)
    }
    return clip(numerator / denominator, lower_bound["input_scale"], upper_bound["input_scale"])
}

function evaluate(k0, cue, mixing, keep,
                  plot, i, n, key, scale, residual, total,
                  prediction_scale, rhs, carbon, isotope, age_moment,
                  respiration) {
    total = 0
    if (k0 < parameter_low[1] || k0 > parameter_high[1] \
            || cue < parameter_low[2] || cue > parameter_high[2] \
            || mixing < parameter_low[3] || mixing > parameter_high[3]) {
        return 1e300
    }
    for (plot in plots) {
        n = layer_count[plot]
        unit_profile(plot, k0, cue, mixing, carbon, respiration, isotope)
        scale = effect_of(plot, carbon, respiration)
        total += active_weight * (scale - 1) ^ 2

        if (keep) {
            delete rhs
            for (i = 1; i <= n; i++) {
                rhs[i] = scale * carbon_input[plot, i]
            }
            solve_rhs(plot, k0, mixing, 0, rhs, carbon)
            for (i = 1; i <= n; i++) {
                respiration[i] = (1 - cue) * decay[plot, i] * carbon[i]
                rhs[i] = scale * carbon_input[plot, i] * input_f14c[plot, i]
            }
            solve_rhs(plot, k0, mixing, lambda14, rhs, isotope)
            delete rhs
            for (i = 1; i <= n; i++) {
                rhs[i] = carbon[i]
            }
            solve_rhs(plot, k0, mixing, 0, rhs, age_moment)
            fitted_scale[plot] = scale
        }

        prediction_scale = keep ? 1 : scale
        for (i = 1; i <= n; i++) {
            key = plot SUBSEP depth_key(depth[plot, i])
            if (trains(plot, i)) {
                residual = (prediction_scale * carbon[i] - observed_carbon[key]) / sigma_carbon[key]
                total += residual ^ 2
                residual = (prediction_scale * respiration[i] - observed_respiration[key]) / sigma_respiration[key]
                total += residual ^ 2
                residual = (isotope[i] / carbon[i] - observed_f14c[key]) / sigma_f14c[key]
                total += residual ^ 2
            }
            if (keep) {
                fitted_carbon[plot, i] = carbon[i]
                fitted_respiration[plot, i] = respiration[i]
                fitted_f14c[plot, i] = isotope[i] / carbon[i]
                fitted_age[plot, i] = age_moment[i] / carbon[i]
            }
        }
    }
    return total
}

function held_out(k0, cue, mixing,
                  plot, i, n, key, scale, residual, total, carbon,
                  respiration, isotope) {
    total = 0
    for (plot in plots) {
        n = layer_count[plot]
        unit_profile(plot, k0, cue, mixing, carbon, respiration, isotope)
        scale = effect_of(plot, carbon, respiration)
        for (i = 1; i <= n; i++) {
            if (trains(plot, i)) {
                continue
            }
            key = plot SUBSEP depth_key(depth[plot, i])
            residual = (scale * carbon[i] - observed_carbon[key]) / sigma_carbon[key]
            total += residual ^ 2
            residual = (scale * respiration[i] - observed_respiration[key]) / sigma_respiration[key]
            total += residual ^ 2
            residual = (isotope[i] / carbon[i] - observed_f14c[key]) / sigma_f14c[key]
            total += residual ^ 2
        }
    }
    return total
}

function evaluate_free(values, dimensions, fixed_index, fixed_value,
                       i, cursor, full) {
    delete full
    cursor = 1
    for (i = 1; i <= 3; i++) {
        if (i == fixed_index) {
            full[i] = fixed_value
        } else {
            full[i] = values[cursor++]
        }
    }
    return evaluate(full[1], full[2], full[3], 0)
}

function consider(values, dimensions, fixed_index, fixed_value,
                  score, j) {
    score = evaluate_free(values, dimensions, fixed_index, fixed_value)
    if (score < search_best) {
        search_best = score
        for (j = 1; j <= dimensions; j++) {
            search_point[j] = values[j]
        }
    }
}

function optimize(fixed_index, fixed_value,
                  dimensions, i, j, a, b, c, iterations, changed, score,
                  trial_score, maximum_fraction, free_index, low, high,
                  point, trial, step, best_full) {
    delete free_index
    delete low
    delete high
    dimensions = 0
    for (i = 1; i <= 3; i++) {
        if (i != fixed_index) {
            dimensions++
            free_index[dimensions] = i
            low[dimensions] = parameter_low[i]
            high[dimensions] = parameter_high[i]
        }
    }
    search_best = 1e300
    delete search_point
    if (dimensions == 3) {
        for (a = 0; a <= 8; a++) {
            point[1] = low[1] + (high[1] - low[1]) * a / 8
            for (b = 0; b <= 8; b++) {
                point[2] = low[2] + (high[2] - low[2]) * b / 8
                for (c = 0; c <= 8; c++) {
                    point[3] = low[3] + (high[3] - low[3]) * c / 8
                    consider(point, dimensions, fixed_index, fixed_value)
                }
            }
        }
    } else if (dimensions == 2) {
        for (a = 0; a <= 6; a++) {
            point[1] = low[1] + (high[1] - low[1]) * a / 6
            for (b = 0; b <= 6; b++) {
                point[2] = low[2] + (high[2] - low[2]) * b / 6
                consider(point, dimensions, fixed_index, fixed_value)
            }
        }
    }
    for (j = 1; j <= dimensions; j++) {
        point[j] = search_point[j]
        step[j] = (high[j] - low[j]) / 8
    }
    score = search_best
    for (iterations = 1; iterations <= 180; iterations++) {
        changed = 0
        for (j = 1; j <= dimensions; j++) {
            for (i = 1; i <= dimensions; i++) {
                trial[i] = point[i]
            }
            trial[j] = clip(point[j] - step[j], low[j], high[j])
            trial_score = evaluate_free(trial, dimensions, fixed_index, fixed_value)
            if (trial_score < score) {
                for (i = 1; i <= dimensions; i++) {
                    point[i] = trial[i]
                }
                score = trial_score
                changed = 1
            }
            for (i = 1; i <= dimensions; i++) {
                trial[i] = point[i]
            }
            trial[j] = clip(point[j] + step[j], low[j], high[j])
            trial_score = evaluate_free(trial, dimensions, fixed_index, fixed_value)
            if (trial_score < score) {
                for (i = 1; i <= dimensions; i++) {
                    point[i] = trial[i]
                }
                score = trial_score
                changed = 1
            }
        }
        if (!changed) {
            maximum_fraction = 0
            for (j = 1; j <= dimensions; j++) {
                step[j] /= 2
                if (step[j] / (high[j] - low[j]) > maximum_fraction) {
                    maximum_fraction = step[j] / (high[j] - low[j])
                }
            }
            if (maximum_fraction < 2e-8) {
                break
            }
        }
    }
    delete best_full
    c = 1
    for (i = 1; i <= 3; i++) {
        if (i == fixed_index) {
            best_full[i] = fixed_value
        } else {
            best_full[i] = point[c++]
        }
        optimized_parameter[i] = best_full[i]
    }
    return score
}

function profile_endpoint(parameter_number, direction, optimum, target,
                          bad, good, middle, value, iteration) {
    if (direction < 0) {
        bad = parameter_low[parameter_number]
    } else {
        bad = parameter_high[parameter_number]
    }
    good = optimum
    value = optimize(parameter_number, bad)
    if (value <= target) {
        return bad
    }
    for (iteration = 1; iteration <= 32; iteration++) {
        middle = (bad + good) / 2
        value = optimize(parameter_number, middle)
        if (value > target) {
            bad = middle
        } else {
            good = middle
        }
    }
    return (bad + good) / 2
}

function validate_inputs(plot, i, key, name, label, labels) {
    for (name in required_bound) {
        if (bound_seen[name] != 1 || lower_bound[name] >= upper_bound[name]) {
            fail("invalid bounds")
        }
    }
    if (weight_count == 0) {
        fail("no candidate penalty weights")
    }
    for (i = 1; i <= weight_count; i++) {
        if (candidate_weight[i] <= 0) {
            fail("nonpositive penalty weight")
        }
    }
    labels = 0
    for (label in fold_present) {
        labels++
    }
    if (labels < 2) {
        fail("fewer than two folds")
    }
    if (length(plots) == 0) {
        fail("no plots")
    }
    for (plot in plots) {
        if (forcing_seen[plot] != 1 || observation_count[plot] != layer_count[plot]) {
            fail("inconsistent plot depth sets")
        }
        if (moisture_scale[plot] <= 0 || oxygen_scale[plot] <= 0) {
            fail("invalid forcing")
        }
        for (i = 1; i <= layer_count[plot]; i++) {
            key = plot SUBSEP depth_key(depth[plot, i])
            if (observation_seen[key] != 1) {
                fail("inconsistent plot depth sets")
            }
            if (sigma_carbon[key] <= 0 || sigma_respiration[key] <= 0 || sigma_f14c[key] <= 0) {
                fail("nonpositive uncertainty")
            }
            if (moisture[plot, i] <= 0 || carbon_input[plot, i] <= 0 \
                    || 1 - 0.35 * clay[plot, i] <= 0) {
                fail("singular profile system")
            }
        }
    }
}

END {
    required_bound["k0"] = 1
    required_bound["cue"] = 1
    required_bound["v"] = 1
    required_bound["input_scale"] = 1
    validate_inputs()

    parameter_name[1] = "k0"
    parameter_name[2] = "cue"
    parameter_name[3] = "v"
    for (i = 1; i <= 3; i++) {
        parameter_low[i] = lower_bound[parameter_name[i]]
        parameter_high[i] = upper_bound[parameter_name[i]]
    }

    ascending(candidate_weight, weight_count)
    fold_total = 0
    for (label in fold_present) {
        fold_label[++fold_total] = label + 0
    }
    ascending(fold_label, fold_total)

    best_index = 0
    for (g = 1; g <= weight_count; g++) {
        active_weight = candidate_weight[g]
        holdout_active = 1
        loss = 0
        for (f = 1; f <= fold_total; f++) {
            holdout_label = fold_label[f]
            optimize(0, 0)
            loss += held_out(optimized_parameter[1], optimized_parameter[2], optimized_parameter[3])
        }
        holdout_active = 0
        train_loss[g] = optimize(0, 0)
        for (i = 1; i <= 3; i++) {
            train_parameter[g, i] = optimized_parameter[i]
        }
        held_loss[g] = loss
        if (best_index == 0 || loss < held_loss[best_index]) {
            best_index = g
        }
    }

    active_weight = candidate_weight[best_index]
    minimum = train_loss[best_index]
    for (i = 1; i <= 3; i++) {
        fitted_parameter[i] = train_parameter[best_index, i]
    }
    target = minimum + 3.841459
    for (i = 1; i <= 3; i++) {
        interval_low[i] = profile_endpoint(i, -1, fitted_parameter[i], target)
        interval_high[i] = profile_endpoint(i, 1, fitted_parameter[i], target)
    }
    final_score = evaluate(fitted_parameter[1], fitted_parameter[2], fitted_parameter[3], 1)

    print "BEGIN IMMEDIATE;"
    print "DROP TABLE IF EXISTS fit_summary;"
    print "DROP TABLE IF EXISTS cv_scores;"
    print "DROP TABLE IF EXISTS fit_limits;"
    print "DROP TABLE IF EXISTS plot_fit;"
    print "DROP TABLE IF EXISTS profile;"
    print "CREATE TABLE fit_summary(k0 REAL NOT NULL, cue REAL NOT NULL, v REAL NOT NULL, penalty REAL NOT NULL, objective REAL NOT NULL);"
    print "CREATE TABLE cv_scores(weight REAL PRIMARY KEY, heldout_loss REAL NOT NULL, train_loss REAL NOT NULL);"
    print "CREATE TABLE fit_limits(parameter TEXT PRIMARY KEY, lower REAL NOT NULL, upper REAL NOT NULL);"
    print "CREATE TABLE plot_fit(plot TEXT PRIMARY KEY, input_scale REAL NOT NULL);"
    print "CREATE TABLE profile(plot TEXT NOT NULL, depth REAL NOT NULL, carbon_hat REAL NOT NULL, respiration_hat REAL NOT NULL, f14c_hat REAL NOT NULL, mean_age REAL NOT NULL, PRIMARY KEY(plot, depth));"
    printf "INSERT INTO fit_summary VALUES(%.15g,%.15g,%.15g,%.15g,%.15g);\n", fitted_parameter[1], fitted_parameter[2], fitted_parameter[3], active_weight, final_score
    for (g = 1; g <= weight_count; g++) {
        printf "INSERT INTO cv_scores VALUES(%.15g,%.15g,%.15g);\n", candidate_weight[g], held_loss[g], train_loss[g]
    }
    for (i = 1; i <= 3; i++) {
        printf "INSERT INTO fit_limits VALUES(%s,%.15g,%.15g);\n", sql_text(parameter_name[i]), interval_low[i], interval_high[i]
    }
    for (plot in plots) {
        printf "INSERT INTO plot_fit VALUES(%s,%.15g);\n", sql_text(plot), fitted_scale[plot]
        for (i = 1; i <= layer_count[plot]; i++) {
            printf "INSERT INTO profile VALUES(%s,%.15g,%.15g,%.15g,%.15g,%.15g);\n", \
                sql_text(plot), depth[plot, i], fitted_carbon[plot, i], \
                fitted_respiration[plot, i], fitted_f14c[plot, i], fitted_age[plot, i]
        }
    }
    print "COMMIT;"
}
