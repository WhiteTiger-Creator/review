args <- commandArgs(trailingOnly = TRUE)
data_dir <- if (length(args) >= 1) args[[1]] else "/app/data"
output_file <- if (length(args) >= 2) args[[2]] else "/app/outputs/results.csv"

Sys.setlocale("LC_COLLATE", "C")
Sys.setlocale("LC_NUMERIC", "C")

fail <- function(message) {
  writeLines(message, con = stderr())
  quit(save = "no", status = 2)
}

required_cases <- c(
  "case_id", "alpha", "gamma", "budget", "min_ess", "ridge",
  "history_horizon", "stability_limit", "pair_budget", "interaction_limit"
  , "switch_gain", "dispersion_penalty", "dispersion_limit",
  "max_concentration", "mixture_units"
)
required_records <- c(
  "case_id", "policy_id", "cluster", "t", "state", "next_state", "action",
  "group", "item_id", "reward", "cost", "x1", "x2", "target_prob",
  "behavior_prob", "source_id"
)
integer_columns <- c(
  "cluster", "t", "state", "next_state", "action", "group", "item_id"
)
record_numeric <- c(
  integer_columns, "reward", "cost", "x1", "x2", "target_prob", "behavior_prob"
)
case_numeric <- c(
  "alpha", "gamma", "budget", "min_ess", "ridge", "history_horizon",
  "stability_limit", "pair_budget", "interaction_limit", "switch_gain",
  "dispersion_penalty", "dispersion_limit", "max_concentration",
  "mixture_units"
)

load_table <- function(path, required) {
  if (!file.exists(path)) {
    fail(paste("missing input", path))
  }
  value <- tryCatch(
    read.csv(path, stringsAsFactors = FALSE, check.names = FALSE),
    error = function(e) fail(paste("invalid CSV", path))
  )
  if (length(setdiff(required, names(value))) != 0) {
    fail(paste("missing required header in", path))
  }
  value
}

finite_numeric <- function(frame, columns) {
  for (column in columns) {
    parsed <- suppressWarnings(as.numeric(frame[[column]]))
    if (any(is.na(parsed)) || any(!is.finite(parsed))) {
      fail(paste("invalid numeric field", column))
    }
    frame[[column]] <- parsed
  }
  frame
}

cases <- load_table(file.path(data_dir, "cases.csv"), required_cases)
records <- load_table(file.path(data_dir, "records.csv"), required_records)
if (nrow(cases) == 0 || nrow(records) == 0 || anyDuplicated(cases$case_id)) {
  fail("empty input or duplicate case_id")
}
cases <- finite_numeric(cases, case_numeric)
records <- finite_numeric(records, record_numeric)

for (column in integer_columns) {
  if (any(records[[column]] != floor(records[[column]]))) {
    fail(paste("non-integer field", column))
  }
}
if (any(cases$history_horizon != floor(cases$history_horizon))) {
  fail("history_horizon must be an integer")
}
if (any(cases$mixture_units != floor(cases$mixture_units))) {
  fail("mixture_units must be an integer")
}
bad_identifier <- function(value) {
  !grepl("^[\\x20-\\x7e]+$", value, perl = TRUE) ||
    grepl("[|,:+@\\r\\n]", value, perl = TRUE)
}
for (column in c("case_id", "policy_id", "source_id")) {
  if (any(vapply(records[[column]], bad_identifier, logical(1)))) {
    fail(paste("invalid identifier", column))
  }
}
if (any(vapply(cases$case_id, bad_identifier, logical(1)))) {
  fail("invalid case identifier")
}
if (
  any(!records$group %in% c(0, 1)) ||
    any(records$target_prob <= 0) ||
    any(records$behavior_prob <= 0) ||
    any(cases$alpha <= 0) ||
    any(cases$gamma < 0) ||
    any(cases$budget < 0) ||
    any(cases$min_ess <= 0) ||
    any(cases$ridge <= 0) ||
    any(cases$history_horizon <= 0) ||
    any(cases$stability_limit < 0) ||
    any(cases$pair_budget < 0) ||
    any(cases$interaction_limit < 0) ||
    any(cases$switch_gain < 0) ||
    any(cases$dispersion_penalty < 0) ||
    any(cases$dispersion_limit < 0) ||
    any(cases$max_concentration < 0.25) ||
    any(cases$max_concentration > 1) ||
    any(cases$mixture_units < 4) ||
    any(cases$mixture_units > 8)
) {
  fail("input is outside the valid domain")
}
if (!setequal(unique(records$case_id), cases$case_id)) {
  fail("case identifiers do not match")
}
keys <- paste(
  records$case_id, records$policy_id, records$cluster, records$t, sep = "\034"
)
if (anyDuplicated(keys)) {
  fail("duplicate event key")
}

for (case_id in cases$case_id) {
  case_rows <- records[records$case_id == case_id, , drop = FALSE]
  if (length(unique(case_rows$policy_id)) != 4 ||
      length(unique(case_rows$cluster)) != 4) {
    fail("invalid policy or cluster cardinality")
  }
  for (policy_id in unique(case_rows$policy_id)) {
    policy_rows <- case_rows[case_rows$policy_id == policy_id, , drop = FALSE]
    if (!setequal(unique(policy_rows$cluster), unique(case_rows$cluster))) {
      fail("policy does not cover every cluster")
    }
    for (cluster_id in unique(policy_rows$cluster)) {
      cluster_rows <- policy_rows[
        policy_rows$cluster == cluster_id, , drop = FALSE
      ]
      if (any(diff(sort(cluster_rows$t)) <= 0)) {
        fail("times are not strictly increasing")
      }
      retained <- policy_rows[
        policy_rows$cluster != cluster_id, , drop = FALSE
      ]
      if (!setequal(unique(retained$group), c(0, 1))) {
        fail("a deletion removes one event group")
      }
    }
    cluster_pairs <- combn(
      sort(unique(policy_rows$cluster)),
      2,
      simplify = FALSE
    )
    for (cluster_pair in cluster_pairs) {
      retained <- policy_rows[
        !policy_rows$cluster %in% cluster_pair, , drop = FALSE
      ]
      if (!setequal(unique(retained$group), c(0, 1))) {
        fail("a pair deletion removes one event group")
      }
    }
  }
}

design_matrix <- function(rows) {
  cbind(
    1,
    rows$x1,
    rows$x2,
    rows$x1 * rows$x2,
    as.numeric(rows$action == rows$next_state)
  )
}

cross_fitted_scores <- function(rows, gamma, ridge) {
  rows$w <- rows$target_prob / rows$behavior_prob
  rows$y <- rows$reward - gamma * rows$cost
  rows$q <- NA_real_
  penalty <- diag(c(0, rep(ridge, 4)))
  for (cluster_id in sort(unique(rows$cluster))) {
    held_out <- rows$cluster == cluster_id
    train <- rows[!held_out, , drop = FALSE]
    test <- rows[held_out, , drop = FALSE]
    train_x <- design_matrix(train)
    rhs <- crossprod(train_x, train$w * train$y)
    system <- crossprod(train_x, train$w * train_x) + penalty
    coefficients <- tryCatch(
      solve(system, rhs),
      error = function(e) fail("ridge system is not solvable")
    )
    prediction <- as.numeric(design_matrix(test) %*% coefficients)
    rows$q[held_out] <- prediction + test$w * (test$y - prediction)
  }
  if (any(!is.finite(rows$q))) {
    fail("non-finite cross-fitted score")
  }
  rows
}

perron_root <- function(matrix_value) {
  a <- matrix_value[1, 1]
  b <- matrix_value[1, 2]
  c <- matrix_value[2, 1]
  d <- matrix_value[2, 2]
  (a + d + sqrt((a - d)^2 + 4 * b * c)) / 2
}

base_metric <- function(rows, alpha, gamma, ridge, horizon) {
  rows <- cross_fitted_scores(rows, gamma, ridge)
  h <- matrix(0.005, nrow = 2, ncol = 2)
  for (cluster_id in sort(unique(rows$cluster))) {
    block <- rows[rows$cluster == cluster_id, , drop = FALSE]
    block <- block[order(block$t), , drop = FALSE]
    if (nrow(block) < 2) {
      next
    }
    for (later in 2:nrow(block)) {
      for (earlier in seq_len(later - 1)) {
        lag <- block$t[later] - block$t[earlier]
        if (lag > horizon) {
          next
        }
        contribution <- sqrt(block$w[earlier] * block$w[later]) *
          exp(-alpha * lag) *
          (1 + gamma * (
            block$next_state[earlier] == block$state[later]
          )) *
          (1 + 0.15 * abs(block$q[earlier] - block$q[later]))
        from <- block$group[earlier] + 1
        to <- block$group[later] + 1
        h[from, to] <- h[from, to] + contribution
      }
    }
  }
  b <- h
  for (group_index in 1:2) {
    b[group_index, ] <- h[group_index, ] / (4 + sum(h[group_index, ]))
  }
  risk <- perron_root(b)
  mass <- c(
    sum(rows$w[rows$group == 0]),
    sum(rows$w[rows$group == 1])
  )
  marks <- c(
    sum(rows$w[rows$group == 0] * rows$q[rows$group == 0]) / mass[1],
    sum(rows$w[rows$group == 1] * rows$q[rows$group == 1]) / mass[2]
  )
  propagated <- tryCatch(
    as.numeric(solve(diag(2) - b, marks)),
    error = function(e) fail("branching system is not solvable")
  )
  objective <- sum((mass / sum(mass)) * propagated)
  cluster_ids <- sort(unique(rows$cluster))
  cluster_mass <- matrix(
    0,
    nrow = 2,
    ncol = length(cluster_ids),
    dimnames = list(c("0", "1"), sprintf("%.0f", cluster_ids))
  )
  for (group_value in 0:1) {
    for (cluster_index in seq_along(cluster_ids)) {
      cluster_mass[group_value + 1, cluster_index] <- sum(
        rows$w[
          rows$group == group_value &
            rows$cluster == cluster_ids[[cluster_index]]
        ]
      )
    }
  }
  group_ess <- apply(
    cluster_mass,
    1,
    function(values) sum(values)^2 / sum(values^2)
  )
  scalars <- c(value = objective, risk = risk, ess = min(group_ess))
  if (any(!is.finite(scalars))) {
    fail("non-finite candidate metric")
  }
  list(
    value = objective,
    risk = risk,
    ess = min(group_ess),
    branching = b,
    marks = marks,
    shares = mass / sum(mass),
    cluster_mass = cluster_mass
  )
}

integer_compositions <- function(total, parts) {
  values <- list()
  visit <- function(prefix, remaining, positions) {
    if (positions == 1) {
      values[[length(values) + 1]] <<- c(prefix, remaining)
      return(invisible(NULL))
    }
    for (value in 0:remaining) {
      visit(c(prefix, value), remaining - value, positions - 1)
    }
    invisible(NULL)
  }
  visit(integer(), total, parts)
  do.call(rbind, values)
}

portfolio_metric <- function(base, counts, case) {
  policies <- names(base)
  lambda <- counts / sum(counts)
  mixed_branching <- matrix(0, nrow = 2, ncol = 2)
  mixed_marks <- numeric(2)
  mixed_shares <- numeric(2)
  mixed_mass <- matrix(
    0,
    nrow = 2,
    ncol = ncol(base[[1]]$cluster_mass),
    dimnames = dimnames(base[[1]]$cluster_mass)
  )
  for (index in seq_along(policies)) {
    mixed_branching <- mixed_branching +
      lambda[[index]] * base[[index]]$branching
    mixed_marks <- mixed_marks + lambda[[index]] * base[[index]]$marks
    mixed_shares <- mixed_shares + lambda[[index]] * base[[index]]$shares
    mixed_mass <- mixed_mass +
      lambda[[index]] * base[[index]]$cluster_mass
  }
  for (left in seq_len(length(policies) - 1)) {
    for (right in seq.int(left + 1, length(policies))) {
      mixed_branching <- mixed_branching +
        case$switch_gain * lambda[[left]] * lambda[[right]] *
          sqrt(base[[left]]$branching * base[[right]]$branching)
    }
  }
  propagated <- tryCatch(
    as.numeric(solve(diag(2) - mixed_branching, mixed_marks)),
    error = function(e) fail("portfolio branching system is not solvable")
  )
  objective <- sum(mixed_shares * propagated)
  risk <- perron_root(mixed_branching)
  group_ess <- apply(
    mixed_mass,
    1,
    function(values) sum(values)^2 / sum(values^2)
  )
  base_values <- vapply(base, function(value) value$value, numeric(1))
  center <- sum(lambda * base_values)
  dispersion <- sqrt(sum(lambda * (base_values - center)^2))
  concentration <- sum(lambda^2)
  result <- c(
    value = objective,
    risk = risk,
    ess = min(group_ess),
    dispersion = dispersion,
    concentration = concentration
  )
  if (any(!is.finite(result))) {
    fail("non-finite portfolio metric")
  }
  result
}

portfolio_code <- function(policies, counts) {
  retained <- which(counts > 0)
  paste(
    paste0(policies[retained], "@", counts[retained]),
    collapse = "+"
  )
}

evaluate_surface <- function(rows, case) {
  policies <- sort(unique(rows$policy_id), method = "radix")
  base <- lapply(
    policies,
    function(policy) base_metric(
      rows[rows$policy_id == policy, , drop = FALSE],
      case$alpha,
      case$gamma,
      case$ridge,
      case$history_horizon
    )
  )
  names(base) <- policies
  compositions <- integer_compositions(case$mixture_units, length(policies))
  concentrations <- apply(
    compositions,
    1,
    function(counts) sum((counts / case$mixture_units)^2)
  )
  compositions <- compositions[
    concentrations <= case$max_concentration,
    ,
    drop = FALSE
  ]
  if (nrow(compositions) == 0) {
    fail("portfolio grid is empty")
  }
  result <- lapply(
    seq_len(nrow(compositions)),
    function(index) portfolio_metric(base, compositions[index, ], case)
  )
  names(result) <- vapply(
    seq_len(nrow(compositions)),
    function(index) portfolio_code(policies, compositions[index, ]),
    character(1)
  )
  result
}

evaluate_full <- function(rows, case) {
  full <- evaluate_surface(rows, case)
  clusters <- sort(unique(rows$cluster))
  deletions <- lapply(
    clusters,
    function(cluster_id) {
      evaluate_surface(rows[rows$cluster != cluster_id, , drop = FALSE], case)
    }
  )
  names(deletions) <- sprintf("%.0f", clusters)
  cluster_pairs <- combn(clusters, 2, simplify = FALSE)
  pairs <- lapply(
    cluster_pairs,
    function(cluster_pair) {
      evaluate_surface(
        rows[!rows$cluster %in% cluster_pair, , drop = FALSE],
        case
      )
    }
  )
  names(pairs) <- vapply(
    cluster_pairs,
    function(cluster_pair) {
      paste(sprintf("%.0f", cluster_pair), collapse = "+")
    },
    character(1)
  )
  enriched <- lapply(
    names(full),
    function(policy) {
      deletion_values <- vapply(
        deletions,
        function(surface) surface[[policy]][["value"]],
        numeric(1)
      )
      deletion_risks <- vapply(
        deletions,
        function(surface) surface[[policy]][["risk"]],
        numeric(1)
      )
      pair_values <- vapply(
        pairs,
        function(surface) surface[[policy]][["value"]],
        numeric(1)
      )
      pair_risks <- vapply(
        pairs,
        function(surface) surface[[policy]][["risk"]],
        numeric(1)
      )
      pair_ess <- vapply(
        pairs,
        function(surface) surface[[policy]][["ess"]],
        numeric(1)
      )
      interactions <- vapply(
        seq_along(cluster_pairs),
        function(pair_index) {
          names_value <- sprintf("%.0f", cluster_pairs[[pair_index]])
          pair_values[[pair_index]] -
            deletions[[names_value[[1]]]][[policy]][["value"]] -
            deletions[[names_value[[2]]]][[policy]][["value"]] +
            full[[policy]][["value"]]
        },
        numeric(1)
      )
      instability <- max(abs(deletion_values - full[[policy]][["value"]]))
      worst_risk <- max(deletion_risks)
      second_order <- max(abs(interactions))
      worst_pair_risk <- max(pair_risks)
      minimum_pair_ess <- min(pair_ess)
      robust <- full[[policy]][["value"]] -
        case$gamma * instability -
        0.5 * (1 + case$gamma) * second_order -
        0.5 * max(0, worst_risk - case$budget) -
        0.75 * max(0, worst_pair_risk - case$pair_budget) -
        case$dispersion_penalty * full[[policy]][["dispersion"]]
      c(
        full[[policy]],
        robust = robust,
        instability = instability,
        worst_risk = worst_risk,
        second_order = second_order,
        worst_pair_risk = worst_pair_risk,
        minimum_pair_ess = minimum_pair_ess
      )
    }
  )
  names(enriched) <- names(full)
  list(
    full = enriched,
    deletions = deletions,
    pairs = pairs,
    cluster_pairs = cluster_pairs
  )
}

select_full <- function(metrics, case) {
  portfolios <- names(metrics)
  robust <- vapply(metrics, function(value) value[["robust"]], numeric(1))
  objective <- vapply(metrics, function(value) value[["value"]], numeric(1))
  risk <- vapply(metrics, function(value) value[["risk"]], numeric(1))
  ess <- vapply(metrics, function(value) value[["ess"]], numeric(1))
  instability <- vapply(
    metrics,
    function(value) value[["instability"]],
    numeric(1)
  )
  worst_risk <- vapply(
    metrics,
    function(value) value[["worst_risk"]],
    numeric(1)
  )
  second_order <- vapply(
    metrics,
    function(value) value[["second_order"]],
    numeric(1)
  )
  worst_pair_risk <- vapply(
    metrics,
    function(value) value[["worst_pair_risk"]],
    numeric(1)
  )
  minimum_pair_ess <- vapply(
    metrics,
    function(value) value[["minimum_pair_ess"]],
    numeric(1)
  )
  dispersion <- vapply(
    metrics,
    function(value) value[["dispersion"]],
    numeric(1)
  )
  concentration <- vapply(
    metrics,
    function(value) value[["concentration"]],
    numeric(1)
  )
  feasible <- risk <= case$budget &
    worst_risk <= case$budget &
    worst_pair_risk <= case$pair_budget &
    ess >= case$min_ess &
    minimum_pair_ess >= case$min_ess / 2 &
    instability <= case$stability_limit &
    second_order <= case$interaction_limit &
    dispersion <= case$dispersion_limit &
    concentration <= case$max_concentration
  pool <- if (any(feasible)) which(feasible) else seq_along(portfolios)
  selected_index <- pool[order(
    -robust[pool],
    -objective[pool],
    dispersion[pool],
    concentration[pool],
    second_order[pool],
    worst_pair_risk[pool],
    worst_risk[pool],
    -minimum_pair_ess[pool],
    -ess[pool],
    portfolios[pool],
    method = "radix"
  )[1]]
  list(
    portfolio = portfolios[selected_index],
    feasible_count = sum(feasible),
    metric = metrics[[selected_index]]
  )
}

select_deletion <- function(metrics, children, case) {
  portfolios <- names(metrics)
  objective <- vapply(metrics, function(value) value[["value"]], numeric(1))
  risk <- vapply(metrics, function(value) value[["risk"]], numeric(1))
  ess <- vapply(metrics, function(value) value[["ess"]], numeric(1))
  dispersion <- vapply(
    metrics,
    function(value) value[["dispersion"]],
    numeric(1)
  )
  concentration <- vapply(
    metrics,
    function(value) value[["concentration"]],
    numeric(1)
  )
  child_values <- lapply(
    portfolios,
    function(portfolio) {
      vapply(
        children,
        function(surface) surface[[portfolio]][["value"]],
        numeric(1)
      )
    }
  )
  child_risks <- lapply(
    portfolios,
    function(portfolio) {
      vapply(
        children,
        function(surface) surface[[portfolio]][["risk"]],
        numeric(1)
      )
    }
  )
  child_ess <- lapply(
    portfolios,
    function(portfolio) {
      vapply(
        children,
        function(surface) surface[[portfolio]][["ess"]],
        numeric(1)
      )
    }
  )
  child_instability <- vapply(
    seq_along(portfolios),
    function(index) {
      max(abs(child_values[[index]] - objective[[index]]))
    },
    numeric(1)
  )
  child_worst_risk <- vapply(child_risks, max, numeric(1))
  child_minimum_ess <- vapply(child_ess, min, numeric(1))
  robust <- objective -
    case$gamma * child_instability -
    0.75 * pmax(0, child_worst_risk - case$pair_budget) -
    case$dispersion_penalty * dispersion
  feasible <- risk <= case$budget &
    child_worst_risk <= case$pair_budget &
    ess >= 3 * case$min_ess / 4 &
    child_minimum_ess >= case$min_ess / 2 &
    child_instability <= case$stability_limit &
    dispersion <= case$dispersion_limit &
    concentration <= case$max_concentration
  pool <- if (any(feasible)) which(feasible) else seq_along(portfolios)
  selected_index <- pool[order(
    -robust[pool],
    -objective[pool],
    dispersion[pool],
    concentration[pool],
    child_instability[pool],
    child_worst_risk[pool],
    risk[pool],
    -child_minimum_ess[pool],
    -ess[pool],
    portfolios[pool],
    method = "radix"
  )[1]]
  list(
    portfolio = portfolios[selected_index],
    metric = metrics[[selected_index]],
    robust = robust[[selected_index]],
    child_instability = child_instability[[selected_index]],
    child_worst_risk = child_worst_risk[[selected_index]],
    child_minimum_ess = child_minimum_ess[[selected_index]]
  )
}

select_pair <- function(metrics, case) {
  portfolios <- names(metrics)
  objective <- vapply(metrics, function(value) value[["value"]], numeric(1))
  risk <- vapply(metrics, function(value) value[["risk"]], numeric(1))
  ess <- vapply(metrics, function(value) value[["ess"]], numeric(1))
  dispersion <- vapply(
    metrics,
    function(value) value[["dispersion"]],
    numeric(1)
  )
  concentration <- vapply(
    metrics,
    function(value) value[["concentration"]],
    numeric(1)
  )
  feasible <- risk <= case$pair_budget &
    ess >= case$min_ess / 2 &
    dispersion <= case$dispersion_limit &
    concentration <= case$max_concentration
  pool <- if (any(feasible)) which(feasible) else seq_along(portfolios)
  selected_index <- pool[order(
    -objective[pool],
    dispersion[pool],
    concentration[pool],
    risk[pool],
    -ess[pool],
    portfolios[pool],
    method = "radix"
  )[1]]
  list(
    portfolio = portfolios[selected_index],
    metric = metrics[[selected_index]]
  )
}

integer_code <- function(value, scale) {
  sprintf("%.0f", round(scale * value))
}

signature <- function(payload) {
  accumulator <- 0
  values <- utf8ToInt(payload)
  for (position in seq_along(values)) {
    accumulator <- (
      131 * accumulator + values[[position]] + position
    ) %% 2147483647
  }
  sprintf("%08x", as.integer(accumulator))
}

output_rows <- vector("list", nrow(cases))
for (case_index in seq_len(nrow(cases))) {
  case <- cases[case_index, ]
  case_rows <- records[records$case_id == case$case_id, , drop = FALSE]
  evaluated <- evaluate_full(case_rows, case)
  selected <- select_full(evaluated$full, case)

  deletion_tokens <- character()
  for (cluster_name in names(evaluated$deletions)) {
    child_names <- names(evaluated$pairs)[
      vapply(
        strsplit(names(evaluated$pairs), "+", fixed = TRUE),
        function(pair) cluster_name %in% pair,
        logical(1)
      )
    ]
    deletion_selected <- select_deletion(
      evaluated$deletions[[cluster_name]],
      evaluated$pairs[child_names],
      case
    )
    deletion_tokens <- c(
      deletion_tokens,
      paste(
        cluster_name,
        deletion_selected$portfolio,
        integer_code(deletion_selected$robust, 1e6),
        integer_code(deletion_selected$metric[["value"]], 1e6),
        integer_code(deletion_selected$metric[["risk"]], 1e6),
        integer_code(deletion_selected$child_worst_risk, 1e6),
        integer_code(deletion_selected$child_instability, 1e6),
        integer_code(deletion_selected$metric[["ess"]], 1e6),
        integer_code(deletion_selected$metric[["dispersion"]], 1e6),
        integer_code(deletion_selected$metric[["concentration"]], 1e6),
        sep = ":"
      )
    )
  }
  deletion_code <- paste(deletion_tokens, collapse = "|")
  pair_tokens <- character()
  for (pair_name in names(evaluated$pairs)) {
    pair_selected <- select_pair(evaluated$pairs[[pair_name]], case)
    pair_tokens <- c(
      pair_tokens,
      paste(
        pair_name,
        pair_selected$portfolio,
        integer_code(pair_selected$metric[["value"]], 1e6),
        integer_code(pair_selected$metric[["risk"]], 1e6),
        integer_code(pair_selected$metric[["ess"]], 1e6),
        integer_code(pair_selected$metric[["dispersion"]], 1e6),
        integer_code(pair_selected$metric[["concentration"]], 1e6),
        sep = ":"
      )
    )
  }
  pair_deletion_code <- paste(pair_tokens, collapse = "|")
  payload <- paste(
    case$case_id,
    selected$portfolio,
    deletion_code,
    pair_deletion_code,
    selected$feasible_count,
    integer_code(selected$metric[["robust"]], 1e7),
    integer_code(selected$metric[["value"]], 1e7),
    integer_code(selected$metric[["risk"]], 1e7),
    integer_code(selected$metric[["worst_risk"]], 1e7),
    integer_code(selected$metric[["ess"]], 1e7),
    integer_code(selected$metric[["instability"]], 1e7),
    integer_code(selected$metric[["worst_pair_risk"]], 1e7),
    integer_code(selected$metric[["minimum_pair_ess"]], 1e7),
    integer_code(selected$metric[["second_order"]], 1e7),
    integer_code(selected$metric[["dispersion"]], 1e7),
    integer_code(selected$metric[["concentration"]], 1e7),
    sep = "|"
  )
  output_rows[[case_index]] <- data.frame(
    case_id = case$case_id,
    selected_portfolio = selected$portfolio,
    feasible_count = selected$feasible_count,
    robust_value = selected$metric[["robust"]],
    full_value = selected$metric[["value"]],
    branching_radius = selected$metric[["risk"]],
    worst_deletion_radius = selected$metric[["worst_risk"]],
    worst_pair_radius = selected$metric[["worst_pair_risk"]],
    effective_sample_size = selected$metric[["ess"]],
    pair_effective_sample_size = selected$metric[["minimum_pair_ess"]],
    jackknife_instability = selected$metric[["instability"]],
    second_order_instability = selected$metric[["second_order"]],
    policy_dispersion = selected$metric[["dispersion"]],
    mixture_concentration = selected$metric[["concentration"]],
    deletion_code = deletion_code,
    pair_deletion_code = pair_deletion_code,
    audit_signature = signature(payload),
    stringsAsFactors = FALSE
  )
}

output <- do.call(rbind, output_rows)
dir.create(dirname(output_file), recursive = TRUE, showWarnings = FALSE)
temporary <- paste0(output_file, ".tmp-", Sys.getpid())
options(digits = 17)
write.csv(output, temporary, row.names = FALSE, quote = FALSE)
if (!file.rename(temporary, output_file)) {
  unlink(temporary)
  fail("could not replace output")
}
