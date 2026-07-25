suppressPackageStartupMessages(library(jsonlite))

DATA_PATH <- Sys.getenv("DATA_PATH", "/app/data/train.csv")
CONFIG_DIR <- Sys.getenv("CONFIG_DIR", "/app/config")
OUT_DIR <- Sys.getenv("OUT_DIR", Sys.getenv("OUTPUT_DIR", "/app/outputs"))
dir.create(OUT_DIR, showWarnings = FALSE, recursive = TRUE)

read_config <- function() {
  cfg <- read.csv(file.path(CONFIG_DIR, "model_config.csv"), stringsAsFactors = FALSE)
  values <- as.list(cfg$value)
  names(values) <- cfg$key
  values
}

cfg <- read_config()
roles <- read.csv(file.path(CONFIG_DIR, "feature_roles.csv"), stringsAsFactors = FALSE)
df <- read.csv(DATA_PATH, stringsAsFactors = FALSE, na.strings = c("", "NA", "NaN"))

id_col <- cfg$id_column
split_col <- cfg$split_column
target_col <- cfg$target_column
group_col <- cfg$group_column
mode <- cfg$task_mode
k_grid <- as.integer(strsplit(cfg$k_grid, "\\|")[[1]])
class_order <- if (nzchar(cfg$class_order)) strsplit(cfg$class_order, "\\|")[[1]] else character(0)
positive_class <- cfg$positive_class
features <- roles$feature[roles$role == "feature"]

fit_mask <- df[[split_col]] == "fit"
validation_mask <- df[[split_col]] == "validation"
test_mask <- df[[split_col]] == "test"

clean_numeric <- function(x) {
  y <- suppressWarnings(as.numeric(x))
  y[!is.finite(y)] <- NA_real_
  y
}

fit_encoder <- function(frame, feature_names, role_frame) {
  encoders <- list()
  for (feature in feature_names) {
    dtype <- role_frame$data_type[match(feature, role_frame$feature)]
    if (dtype == "numeric") {
      vals <- clean_numeric(frame[[feature]])
      med <- median(vals, na.rm = TRUE)
      if (!is.finite(med)) {
        med <- 0
      }
      vals[is.na(vals)] <- med
      mu <- mean(vals)
      sig <- stats::sd(vals)
      if (!is.finite(sig) || sig < 1e-9) {
        sig <- 1
      }
      encoders[[feature]] <- list(type = "numeric", median = med, mean = mu, sd = sig)
    } else {
      vals <- as.character(frame[[feature]])
      vals[is.na(vals) | vals == "" | vals == "?" | vals == "MISSING"] <- "__missing__"
      levels <- sort(unique(vals))
      levels <- unique(c(levels, "__missing__", "__other__"))
      encoders[[feature]] <- list(type = "categorical", levels = levels)
    }
  }
  encoders
}

apply_encoder <- function(frame, encoders) {
  parts <- list()
  names_out <- character(0)
  for (feature in names(encoders)) {
    encoder <- encoders[[feature]]
    if (encoder$type == "numeric") {
      vals <- clean_numeric(frame[[feature]])
      vals[is.na(vals)] <- encoder$median
      parts[[length(parts) + 1L]] <- matrix((vals - encoder$mean) / encoder$sd, ncol = 1)
      names_out <- c(names_out, feature)
    } else {
      vals <- as.character(frame[[feature]])
      vals[is.na(vals) | vals == "" | vals == "?" | vals == "MISSING"] <- "__missing__"
      vals[!(vals %in% encoder$levels)] <- "__other__"
      mat <- matrix(0, nrow = nrow(frame), ncol = length(encoder$levels))
      for (j in seq_along(encoder$levels)) {
        mat[, j] <- as.integer(vals == encoder$levels[[j]])
      }
      parts[[length(parts) + 1L]] <- mat
      names_out <- c(names_out, paste(feature, encoder$levels, sep = "__"))
    }
  }
  out <- do.call(cbind, parts)
  colnames(out) <- names_out
  out
}

knn_predict <- function(train_x, train_y, eval_x, k, mode, classes) {
  n_eval <- nrow(eval_x)
  k <- min(k, nrow(train_x))
  if (mode == "regression") {
    pred <- numeric(n_eval)
    lower <- numeric(n_eval)
    upper <- numeric(n_eval)
    first_id <- integer(n_eval)
    first_dist <- numeric(n_eval)
    for (i in seq_len(n_eval)) {
      diffs <- sweep(train_x, 2, eval_x[i, ], "-")
      dist <- sqrt(rowSums(diffs * diffs))
      idx <- order(dist)[seq_len(k)]
      weights <- 1 / (dist[idx] + 1e-6)
      pred[i] <- sum(weights * train_y[idx]) / sum(weights)
      lower[i] <- as.numeric(stats::quantile(train_y[idx], probs = 0.08, names = FALSE, type = 8))
      upper[i] <- as.numeric(stats::quantile(train_y[idx], probs = 0.92, names = FALSE, type = 8))
      first_id[i] <- idx[[1]]
      first_dist[i] <- dist[idx[[1]]]
    }
    return(list(prediction = pred, lower = lower, upper = upper, first_id = first_id, first_dist = first_dist))
  }
  prob <- matrix(0, nrow = n_eval, ncol = length(classes))
  colnames(prob) <- classes
  first_id <- integer(n_eval)
  first_dist <- numeric(n_eval)
  for (i in seq_len(n_eval)) {
    diffs <- sweep(train_x, 2, eval_x[i, ], "-")
    dist <- sqrt(rowSums(diffs * diffs))
    idx <- order(dist)[seq_len(k)]
    weights <- 1 / (dist[idx] + 1e-6)
    for (j in seq_along(classes)) {
      prob[i, j] <- sum(weights[as.character(train_y[idx]) == classes[[j]]])
    }
    denom <- sum(prob[i, ])
    if (denom <= 0) {
      prob[i, ] <- 1 / length(classes)
    } else {
      prob[i, ] <- prob[i, ] / denom
    }
    first_id[i] <- idx[[1]]
    first_dist[i] <- dist[idx[[1]]]
  }
  pred <- classes[max.col(prob, ties.method = "first")]
  list(prob = prob, label = pred, first_id = first_id, first_dist = first_dist)
}

macro_f1 <- function(actual, predicted, classes) {
  vals <- numeric(length(classes))
  for (i in seq_along(classes)) {
    cls <- classes[[i]]
    tp <- sum(actual == cls & predicted == cls)
    fp <- sum(actual != cls & predicted == cls)
    fn <- sum(actual == cls & predicted != cls)
    precision <- if ((tp + fp) == 0) 0 else tp / (tp + fp)
    recall <- if ((tp + fn) == 0) 0 else tp / (tp + fn)
    vals[i] <- if ((precision + recall) == 0) 0 else 2 * precision * recall / (precision + recall)
  }
  mean(vals)
}

binary_f1_at <- function(actual, proba, threshold, positive) {
  predicted <- ifelse(proba >= threshold, positive, setdiff(class_order, positive)[[1]])
  macro_f1(actual, predicted, class_order)
}

select_threshold <- function(actual, proba, positive) {
  grid <- seq(0.15, 0.85, by = 0.02)
  scores <- vapply(grid, function(t) binary_f1_at(actual, proba, t, positive), numeric(1))
  grid[which.max(scores)]
}

regression_scores <- function(actual, pred) {
  rmse <- sqrt(mean((actual - pred) ^ 2))
  mae <- mean(abs(actual - pred))
  denom <- sum((actual - mean(actual)) ^ 2)
  r2 <- if (denom <= 0) 0 else 1 - sum((actual - pred) ^ 2) / denom
  c(rmse = rmse, mae = mae, r2 = r2)
}

group_stability <- function(actual, pred, groups) {
  group_key <- as.character(groups)
  group_key[is.na(group_key) | group_key == ""] <- "__missing__"
  group_values <- sort(unique(group_key))
  rmses <- vapply(group_values, function(g) {
    mask <- group_key == g
    sqrt(mean((actual[mask] - pred[mask]) ^ 2))
  }, numeric(1))
  c(
    worst_group_rmse = max(rmses),
    best_group_rmse = min(rmses),
    stability_gap = max(rmses) - min(rmses)
  )
}

fit_ridge <- function(x, y, lambda) {
  x <- as.matrix(x)
  y <- clean_numeric(y)
  med <- median(y, na.rm = TRUE)
  if (!is.finite(med)) {
    med <- 0
  }
  y[!is.finite(y)] <- med
  design <- cbind(Intercept = 1, x)
  penalty <- diag(ncol(design))
  penalty[1, 1] <- 0
  lhs <- crossprod(design) + lambda * penalty
  rhs <- crossprod(design, y)
  coef <- tryCatch(solve(lhs, rhs), error = function(e) qr.solve(lhs, rhs))
  list(coef = as.numeric(coef))
}

predict_ridge <- function(model, x) {
  design <- cbind(Intercept = 1, as.matrix(x))
  as.numeric(design %*% model$coef)
}

target_for_model <- function(y, use_log) {
  if (use_log) {
    log1p(pmax(y, 0))
  } else {
    y
  }
}

target_from_model <- function(y, use_log) {
  if (use_log) {
    pmax(0, expm1(y))
  } else {
    y
  }
}

safe_name <- function(x) {
  y <- tolower(gsub("[^A-Za-z0-9]", "_", x))
  y <- gsub("^_+|_+$", "", y)
  ifelse(nzchar(y), y, "class")
}

normalize_labels <- function(x, classes) {
  raw <- as.character(x)
  raw[is.na(raw)] <- ""
  if (all(raw %in% classes)) {
    return(raw)
  }
  class_num <- suppressWarnings(as.numeric(classes))
  raw_num <- suppressWarnings(as.numeric(raw))
  if (all(is.finite(class_num))) {
    out <- raw
    for (i in seq_along(out)) {
      if (is.finite(raw_num[[i]])) {
        j <- which.min(abs(class_num - raw_num[[i]]))
        if (abs(class_num[[j]] - raw_num[[i]]) < 1e-8) {
          out[[i]] <- classes[[j]]
        }
      }
    }
    out
  } else {
    raw
  }
}

encoder <- fit_encoder(df[fit_mask, , drop = FALSE], features, roles)
fit_x <- apply_encoder(df[fit_mask, , drop = FALSE], encoder)
validation_x <- apply_encoder(df[validation_mask, , drop = FALSE], encoder)
test_x <- apply_encoder(df[test_mask, , drop = FALSE], encoder)
fit_ids <- df[[id_col]][fit_mask]
validation_ids <- df[[id_col]][validation_mask]
test_ids <- df[[id_col]][test_mask]
validation_groups <- df[[group_col]][validation_mask]
test_groups <- df[[group_col]][test_mask]

selection_rows <- list()
if (mode == "regression") {
  fit_y <- clean_numeric(df[[target_col]][fit_mask])
  validation_y <- clean_numeric(df[[target_col]][validation_mask])
  use_log_target <- min(fit_y, validation_y, na.rm = TRUE) >= 0
  best_metric <- Inf
  best_gap <- Inf
  best_k <- k_grid[[1]]
  for (k in k_grid) {
    model <- fit_ridge(fit_x, target_for_model(fit_y, use_log_target), k)
    p <- target_from_model(predict_ridge(model, validation_x), use_log_target)
    p <- list(prediction = p)
    score <- regression_scores(validation_y, p$prediction)
    stability <- group_stability(validation_y, p$prediction, validation_groups)
    selection_rows[[length(selection_rows) + 1L]] <- data.frame(
      candidate_k = k,
      validation_metric = score[["rmse"]],
      worst_group_rmse = stability[["worst_group_rmse"]],
      best_group_rmse = stability[["best_group_rmse"]],
      stability_gap = stability[["stability_gap"]]
    )
    if (
      stability[["stability_gap"]] < best_gap ||
        (abs(stability[["stability_gap"]] - best_gap) <= 1e-12 && score[["rmse"]] < best_metric) ||
        (abs(stability[["stability_gap"]] - best_gap) <= 1e-12 && abs(score[["rmse"]] - best_metric) <= 1e-12 && k < best_k)
    ) {
      best_gap <- stability[["stability_gap"]]
      best_metric <- score[["rmse"]]
      best_k <- k
    }
  }
  validation_knn <- knn_predict(fit_x, fit_y, validation_x, best_k, mode, class_order)
  validation_model <- fit_ridge(fit_x, target_for_model(fit_y, use_log_target), best_k)
  validation_pred <- validation_knn
  validation_pred$prediction <- target_from_model(predict_ridge(validation_model, validation_x), use_log_target)
  final_mask <- fit_mask | validation_mask
  final_encoder <- fit_encoder(df[final_mask, , drop = FALSE], features, roles)
  final_x <- apply_encoder(df[final_mask, , drop = FALSE], final_encoder)
  final_y <- clean_numeric(df[[target_col]][final_mask])
  final_test_x <- apply_encoder(df[test_mask, , drop = FALSE], final_encoder)
  final_use_log_target <- min(final_y, na.rm = TRUE) >= 0
  test_knn <- knn_predict(final_x, final_y, final_test_x, best_k, mode, class_order)
  final_model <- fit_ridge(final_x, target_for_model(final_y, final_use_log_target), best_k)
  test_pred <- test_knn
  test_pred$prediction <- target_from_model(predict_ridge(final_model, final_test_x), final_use_log_target)
  scores <- regression_scores(validation_y, validation_pred$prediction)
  validation_out <- data.frame(
    row_id = validation_ids,
    actual = round(validation_y, 6),
    prediction = round(validation_pred$prediction, 6),
    residual = round(validation_y - validation_pred$prediction, 6),
    abs_error = round(abs(validation_y - validation_pred$prediction), 6),
    group_key = validation_groups
  )
  write.csv(validation_out[order(validation_out$row_id), ], file.path(OUT_DIR, "validation_predictions.csv"), row.names = FALSE, quote = FALSE)
  pred_out <- data.frame(
    row_id = test_ids,
    prediction = round(test_pred$prediction, 6),
    lower = round(pmin(test_pred$lower, test_pred$upper), 6),
    upper = round(pmax(test_pred$lower, test_pred$upper), 6),
    group_key = test_groups
  )
  write.csv(pred_out[order(pred_out$row_id), ], file.path(OUT_DIR, "predictions.csv"), row.names = FALSE, quote = FALSE)
  interval <- data.frame(
    split = "validation",
    interval_coverage = round(mean(validation_y >= validation_pred$lower & validation_y <= validation_pred$upper), 6),
    mean_width = round(mean(validation_pred$upper - validation_pred$lower), 6)
  )
  write.csv(interval, file.path(OUT_DIR, "interval_report.csv"), row.names = FALSE, quote = FALSE)
  cuts <- stats::quantile(validation_out$prediction, probs = seq(0, 1, length.out = 6), na.rm = TRUE, type = 8)
  cuts <- unique(cuts)
  if (length(cuts) < 2) {
    cuts <- c(min(validation_out$prediction), max(validation_out$prediction) + 1e-6)
  }
  bins <- cut(validation_out$prediction, breaks = cuts, include.lowest = TRUE)
  residual_bins <- aggregate(abs_error ~ bins, data = data.frame(bins = bins, abs_error = validation_out$abs_error), FUN = mean)
  names(residual_bins) <- c("prediction_bin", "mean_abs_error")
  residual_bins$count <- as.integer(tabulate(as.integer(bins), nbins = nrow(residual_bins)))
  write.csv(residual_bins, file.path(OUT_DIR, "residual_bins.csv"), row.names = FALSE, quote = FALSE)
  metrics <- list(
    task_mode = mode,
    target_column = target_col,
    model_family = "scaled_mixed_ridge_knn_evidence",
    selected_k = as.integer(best_k),
    n_fit = as.integer(sum(fit_mask)),
    n_validation = as.integer(sum(validation_mask)),
    n_test = as.integer(sum(test_mask)),
    validation_rmse = round(scores[["rmse"]], 6),
    validation_mae = round(scores[["mae"]], 6),
    validation_r2 = round(scores[["r2"]], 6),
    interval_coverage = interval$interval_coverage[[1]]
  )
} else {
  fit_y <- normalize_labels(df[[target_col]][fit_mask], class_order)
  validation_y <- normalize_labels(df[[target_col]][validation_mask], class_order)
  best_metric <- -Inf
  best_k <- k_grid[[1]]
  for (k in k_grid) {
    p <- knn_predict(fit_x, fit_y, validation_x, k, mode, class_order)
    score <- macro_f1(validation_y, p$label, class_order)
    selection_rows[[length(selection_rows) + 1L]] <- data.frame(candidate_k = k, validation_metric = score)
    if (score > best_metric) {
      best_metric <- score
      best_k <- k
    }
  }
  validation_pred <- knn_predict(fit_x, fit_y, validation_x, best_k, mode, class_order)
  threshold <- 0.5
  if (mode == "binary") {
    pos_index <- match(positive_class, class_order)
    threshold <- select_threshold(validation_y, validation_pred$prob[, pos_index], positive_class)
    neg_class <- setdiff(class_order, positive_class)[[1]]
    validation_pred$label <- ifelse(validation_pred$prob[, pos_index] >= threshold, positive_class, neg_class)
  }
  final_mask <- fit_mask | validation_mask
  final_encoder <- fit_encoder(df[final_mask, , drop = FALSE], features, roles)
  final_x <- apply_encoder(df[final_mask, , drop = FALSE], final_encoder)
  final_y <- normalize_labels(df[[target_col]][final_mask], class_order)
  final_test_x <- apply_encoder(df[test_mask, , drop = FALSE], final_encoder)
  test_pred <- knn_predict(final_x, final_y, final_test_x, best_k, mode, class_order)
  if (mode == "binary") {
    pos_index <- match(positive_class, class_order)
    neg_class <- setdiff(class_order, positive_class)[[1]]
    test_pred$label <- ifelse(test_pred$prob[, pos_index] >= threshold, positive_class, neg_class)
  }
  accuracy <- mean(validation_y == validation_pred$label)
  macro <- macro_f1(validation_y, validation_pred$label, class_order)
  validation_out <- data.frame(
    row_id = validation_ids,
    actual = validation_y,
    pred_label = validation_pred$label,
    correct = as.integer(validation_y == validation_pred$label),
    group_key = validation_groups
  )
  for (cls in class_order) {
    validation_out[[paste0("prob_", safe_name(cls))]] <- round(validation_pred$prob[, match(cls, class_order)], 6)
  }
  write.csv(validation_out[order(validation_out$row_id), ], file.path(OUT_DIR, "validation_predictions.csv"), row.names = FALSE, quote = FALSE)
  pred_out <- data.frame(row_id = test_ids, pred_label = test_pred$label, group_key = test_groups)
  for (cls in class_order) {
    pred_out[[paste0("prob_", safe_name(cls))]] <- round(test_pred$prob[, match(cls, class_order)], 6)
  }
  if (mode == "binary") {
    pred_out$pred_proba <- round(test_pred$prob[, match(positive_class, class_order)], 6)
  }
  write.csv(pred_out[order(pred_out$row_id), ], file.path(OUT_DIR, "predictions.csv"), row.names = FALSE, quote = FALSE)
  confusion <- expand.grid(actual = class_order, predicted = class_order, stringsAsFactors = FALSE)
  confusion$count <- mapply(function(a, p) sum(validation_y == a & validation_pred$label == p), confusion$actual, confusion$predicted)
  write.csv(confusion, file.path(OUT_DIR, "confusion_matrix.csv"), row.names = FALSE, quote = FALSE)
  class_rows <- lapply(class_order, function(cls) {
    tp <- sum(validation_y == cls & validation_pred$label == cls)
    fp <- sum(validation_y != cls & validation_pred$label == cls)
    fn <- sum(validation_y == cls & validation_pred$label != cls)
    precision <- if ((tp + fp) == 0) 0 else tp / (tp + fp)
    recall <- if ((tp + fn) == 0) 0 else tp / (tp + fn)
    f1 <- if ((precision + recall) == 0) 0 else 2 * precision * recall / (precision + recall)
    data.frame(class = cls, precision = round(precision, 6), recall = round(recall, 6), f1 = round(f1, 6), support = sum(validation_y == cls))
  })
  write.csv(do.call(rbind, class_rows), file.path(OUT_DIR, "class_metrics.csv"), row.names = FALSE, quote = FALSE)
  conf_score <- apply(validation_pred$prob, 1, max)
  bins <- cut(conf_score, breaks = seq(0, 1, length.out = 6), include.lowest = TRUE)
  cal <- aggregate(correct ~ bins, data = data.frame(bins = bins, correct = as.integer(validation_y == validation_pred$label)), FUN = mean)
  names(cal) <- c("confidence_bin", "empirical_accuracy")
  cal$count <- as.integer(tabulate(as.integer(bins), nbins = nrow(cal)))
  write.csv(cal, file.path(OUT_DIR, "calibration_bins.csv"), row.names = FALSE, quote = FALSE)
  if (mode == "binary") {
    grid <- seq(0.15, 0.85, by = 0.02)
    pos_index <- match(positive_class, class_order)
    threshold_report <- data.frame(
      threshold = grid,
      macro_f1 = vapply(grid, function(t) binary_f1_at(validation_y, validation_pred$prob[, pos_index], t, positive_class), numeric(1)),
      selected = abs(grid - threshold) < 1e-12
    )
    write.csv(threshold_report, file.path(OUT_DIR, "threshold_report.csv"), row.names = FALSE, quote = FALSE)
  }
  metrics <- list(
    task_mode = mode,
    target_column = target_col,
    model_family = "scaled_mixed_knn",
    selected_k = as.integer(best_k),
    n_fit = as.integer(sum(fit_mask)),
    n_validation = as.integer(sum(validation_mask)),
    n_test = as.integer(sum(test_mask)),
    validation_accuracy = round(accuracy, 6),
    validation_macro_f1 = round(macro, 6),
    operating_threshold = round(threshold, 6)
  )
}

selection_report <- do.call(rbind, selection_rows)
selection_report$selected <- selection_report$candidate_k == metrics$selected_k
write.csv(selection_report, file.path(OUT_DIR, "selection_report.csv"), row.names = FALSE, quote = FALSE)

feature_rows <- lapply(features, function(feature) {
  data.frame(
    feature = feature,
    data_type = roles$data_type[match(feature, roles$feature)],
    missing_fit = sum(is.na(df[[feature]][fit_mask]) | df[[feature]][fit_mask] == ""),
    missing_validation = sum(is.na(df[[feature]][validation_mask]) | df[[feature]][validation_mask] == ""),
    missing_test = sum(is.na(df[[feature]][test_mask]) | df[[feature]][test_mask] == "")
  )
})
write.csv(do.call(rbind, feature_rows), file.path(OUT_DIR, "feature_summary.csv"), row.names = FALSE, quote = FALSE)

if (mode == "regression") {
  group_summary <- aggregate(abs_error ~ group_key, data = validation_out, FUN = mean)
  names(group_summary) <- c("group_key", "mean_abs_error")
  group_summary$n_validation <- as.integer(tabulate(match(validation_out$group_key, group_summary$group_key)))
} else {
  group_summary <- aggregate(correct ~ group_key, data = validation_out, FUN = mean)
  names(group_summary) <- c("group_key", "accuracy")
  group_summary$n_validation <- as.integer(tabulate(match(validation_out$group_key, group_summary$group_key)))
}
write.csv(group_summary, file.path(OUT_DIR, "group_error_report.csv"), row.names = FALSE, quote = FALSE)

neighbor_count <- min(50L, sum(test_mask))
neighbor_rows <- data.frame(
  row_id = test_ids[seq_len(neighbor_count)],
  nearest_fit_index = if (mode == "regression") test_pred$first_id[seq_len(neighbor_count)] else test_pred$first_id[seq_len(neighbor_count)],
  nearest_distance = round(if (mode == "regression") test_pred$first_dist[seq_len(neighbor_count)] else test_pred$first_dist[seq_len(neighbor_count)], 6)
)
write.csv(neighbor_rows, file.path(OUT_DIR, "neighbor_evidence.csv"), row.names = FALSE, quote = FALSE)

write_json(metrics, file.path(OUT_DIR, "metrics.json"), auto_unbox = TRUE, pretty = TRUE, digits = NA)
