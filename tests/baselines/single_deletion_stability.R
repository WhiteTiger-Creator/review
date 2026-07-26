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
  "history_horizon", "stability_limit"
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
  "stability_limit"
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
bad_identifier <- function(value) {
  !grepl("^[\\x20-\\x7e]+$", value, perl = TRUE) ||
    grepl("[|,:\\r\\n]", value, perl = TRUE)
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
    any(cases$min_ess <= 0) ||
    any(cases$ridge <= 0) ||
    any(cases$history_horizon <= 0) ||
    any(cases$stability_limit < 0)
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
  if (length(unique(case_rows$policy_id)) < 2 ||
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
  group_ess <- numeric(2)
  for (group_value in 0:1) {
    by_cluster <- tapply(
      rows$w[rows$group == group_value],
      rows$cluster[rows$group == group_value],
      sum
    )
    group_ess[group_value + 1] <- sum(by_cluster)^2 / sum(by_cluster^2)
  }
  result <- c(value = objective, risk = risk, ess = min(group_ess))
  if (any(!is.finite(result))) {
    fail("non-finite candidate metric")
  }
  result
}

evaluate_surface <- function(rows, case) {
  policies <- sort(unique(rows$policy_id), method = "radix")
  result <- lapply(
    policies,
    function(policy) base_metric(
      rows[rows$policy_id == policy, , drop = FALSE],
      case$alpha,
      case$gamma,
      case$ridge,
      case$history_horizon
    )
  )
  names(result) <- policies
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
      instability <- abs(
        deletion_values[[length(deletion_values)]] -
          full[[policy]][["value"]]
      )
      worst_risk <- deletion_risks[[length(deletion_risks)]]
      robust <- full[[policy]][["value"]] -
        case$gamma * instability -
        0.5 * max(0, worst_risk - case$budget)
      c(
        full[[policy]],
        robust = robust,
        instability = instability,
        worst_risk = worst_risk
      )
    }
  )
  names(enriched) <- names(full)
  list(full = enriched, deletions = deletions)
}

select_full <- function(metrics, case) {
  policies <- names(metrics)
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
  feasible <- risk <= case$budget &
    worst_risk <= case$budget &
    ess >= case$min_ess &
    instability <= case$stability_limit
  pool <- if (any(feasible)) which(feasible) else seq_along(policies)
  selected_index <- pool[order(
    -robust[pool],
    -objective[pool],
    worst_risk[pool],
    -ess[pool],
    policies[pool],
    method = "radix"
  )[1]]
  list(
    policy = policies[selected_index],
    feasible_count = sum(feasible),
    metric = metrics[[selected_index]]
  )
}

select_deletion <- function(metrics, case, cluster_count) {
  policies <- names(metrics)
  objective <- vapply(metrics, function(value) value[["value"]], numeric(1))
  risk <- vapply(metrics, function(value) value[["risk"]], numeric(1))
  ess <- vapply(metrics, function(value) value[["ess"]], numeric(1))
  threshold <- case$min_ess * cluster_count / 4
  feasible <- risk <= case$budget & ess >= threshold
  pool <- if (any(feasible)) which(feasible) else seq_along(policies)
  selected_index <- pool[order(
    -objective[pool],
    risk[pool],
    -ess[pool],
    policies[pool],
    method = "radix"
  )[1]]
  list(policy = policies[selected_index], metric = metrics[[selected_index]])
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
    deletion_selected <- select_deletion(
      evaluated$deletions[[cluster_name]],
      case,
      3
    )
    deletion_tokens <- c(
      deletion_tokens,
      paste(
        cluster_name,
        deletion_selected$policy,
        integer_code(deletion_selected$metric[["value"]], 1e6),
        integer_code(deletion_selected$metric[["risk"]], 1e6),
        integer_code(deletion_selected$metric[["ess"]], 1e6),
        sep = ":"
      )
    )
  }
  deletion_code <- paste(deletion_tokens, collapse = "|")
  payload <- paste(
    case$case_id,
    selected$policy,
    deletion_code,
    selected$feasible_count,
    integer_code(selected$metric[["robust"]], 1e7),
    integer_code(selected$metric[["value"]], 1e7),
    integer_code(selected$metric[["risk"]], 1e7),
    integer_code(selected$metric[["worst_risk"]], 1e7),
    integer_code(selected$metric[["ess"]], 1e7),
    integer_code(selected$metric[["instability"]], 1e7),
    sep = "|"
  )
  output_rows[[case_index]] <- data.frame(
    case_id = case$case_id,
    selected_policy = selected$policy,
    feasible_count = selected$feasible_count,
    robust_value = selected$metric[["robust"]],
    full_value = selected$metric[["value"]],
    branching_radius = selected$metric[["risk"]],
    worst_deletion_radius = selected$metric[["worst_risk"]],
    effective_sample_size = selected$metric[["ess"]],
    jackknife_instability = selected$metric[["instability"]],
    deletion_code = deletion_code,
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
