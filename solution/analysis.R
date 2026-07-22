suppressWarnings(suppressMessages({
  library(MASS)
  library(jsonlite)
}))

DATA_PATH <- Sys.getenv("DATA_PATH", "/app/data")
OUTPUT_PATH <- Sys.getenv("OUTPUT_PATH", "/app/output")
dir.create(OUTPUT_PATH, showWarnings = FALSE, recursive = TRUE)

round6 <- function(x) round(as.numeric(x), 6)

ece <- function(y, p, bins = 10L) {
  p <- pmin(pmax(as.numeric(p), 0), 1)
  y <- as.numeric(y)
  idx <- pmin(as.integer(floor(p * bins)) + 1L, bins)
  total <- length(p)
  score <- 0
  for (b in seq_len(bins)) {
    sel <- which(idx == b)
    if (length(sel) == 0) next
    score <- score + abs(mean(p[sel]) - mean(y[sel])) * length(sel) / total
  }
  as.numeric(score)
}

multiclass_logloss <- function(y, probs, levels) {
  y_idx <- match(y, levels)
  p <- pmin(pmax(probs[cbind(seq_along(y_idx), y_idx)], 1e-15), 1)
  as.numeric(-mean(log(p)))
}

brier_multiclass <- function(y, probs, levels) {
  y_idx <- match(y, levels)
  truth <- matrix(0, nrow = length(y_idx), ncol = length(levels))
  truth[cbind(seq_along(y_idx), y_idx)] <- 1
  as.numeric(mean(rowSums((probs - truth)^2)))
}

read_source <- function(path) {
  df <- read.csv(path, check.names = FALSE, stringsAsFactors = FALSE)
  names(df) <- gsub(" ", "", names(df), fixed = TRUE)
  for (i in seq_len(22)) {
    names(df)[names(df) == paste0("MFCCs_", i)] <- paste0("MFCC_", i)
  }
  required <- c(paste0("MFCC_", seq_len(22)), "Family", "Genus", "Species", "RecordID")
  missing <- setdiff(required, names(df))
  if (length(missing) > 0) stop(paste("missing columns:", paste(missing, collapse = ", ")))
  if (!("row_id" %in% names(df))) {
    df$row_id <- seq_len(nrow(df)) - 1L
  }
  df <- df[, c("row_id", required)]
  df$row_id <- as.integer(df$row_id)
  df$RecordID <- as.integer(df$RecordID)
  df$Family <- trimws(df$Family)
  df$Genus <- trimws(df$Genus)
  df$Species <- trimws(df$Species)
  df
}

source_df <- read_source(file.path(DATA_PATH, "Frogs_MFCCs.csv"))
family_levels <- sort(unique(source_df$Family))
genus_levels <- sort(unique(source_df$Genus))
species_levels <- sort(unique(source_df$Species))

source_df$Family <- factor(source_df$Family, levels = family_levels)
source_df$Genus <- factor(source_df$Genus, levels = genus_levels)
source_df$Species <- factor(source_df$Species, levels = species_levels)

train_raw <- source_df[source_df$row_id %% 5L != 0L, , drop = FALSE]
eval_raw <- source_df[source_df$row_id %% 5L == 0L, , drop = FALSE]

feature_cols <- paste0("MFCC_", seq_len(22))
center <- vapply(train_raw[, feature_cols], mean, numeric(1))
scale <- vapply(train_raw[, feature_cols], sd, numeric(1))
scale[scale == 0] <- 1

scale_frame <- function(df) {
  out <- as.data.frame(Map(function(col, mu, sig) (as.numeric(col) - mu) / sig, df[, feature_cols], center, scale))
  names(out) <- feature_cols
  out
}

train_df <- data.frame(
  Species = train_raw$Species,
  scale_frame(train_raw),
  check.names = FALSE,
  stringsAsFactors = FALSE
)
eval_features <- scale_frame(eval_raw)
train_df$Species <- factor(train_df$Species, levels = species_levels)

fit <- MASS::lda(Species ~ ., data = train_df, prior = rep(1 / length(species_levels), length(species_levels)))
posterior <- predict(fit, newdata = eval_features)$posterior
posterior <- posterior[, species_levels, drop = FALSE]
posterior <- posterior / rowSums(posterior)

species_to_genus <- matrix(0, nrow = length(species_levels), ncol = length(genus_levels))
colnames(species_to_genus) <- genus_levels
rownames(species_to_genus) <- species_levels
species_to_family <- matrix(0, nrow = length(species_levels), ncol = length(family_levels))
colnames(species_to_family) <- family_levels
rownames(species_to_family) <- species_levels
lookup <- unique(source_df[, c("Species", "Genus", "Family")])
for (i in seq_len(nrow(lookup))) {
  species_to_genus[as.character(lookup$Species[i]), as.character(lookup$Genus[i])] <- 1
  species_to_family[as.character(lookup$Species[i]), as.character(lookup$Family[i])] <- 1
}

genus_probs <- posterior %*% species_to_genus
family_probs <- posterior %*% species_to_family
genus_probs <- genus_probs / rowSums(genus_probs)
family_probs <- family_probs / rowSums(family_probs)

pred_species_idx <- max.col(posterior, ties.method = "first")
pred_genus_idx <- max.col(genus_probs, ties.method = "first")
pred_family_idx <- max.col(family_probs, ties.method = "first")
pred_abstain <- as.integer(apply(posterior, 1, max) < 0.55)

predictions <- data.frame(
  row_id = eval_raw$row_id,
  RecordID = eval_raw$RecordID,
  pred_family = family_levels[pred_family_idx],
  pred_genus = genus_levels[pred_genus_idx],
  pred_species = species_levels[pred_species_idx],
  pred_abstain = pred_abstain,
  stringsAsFactors = FALSE
)

for (nm in family_levels) predictions[[paste0("prob_family_", nm)]] <- round6(family_probs[, nm])
for (nm in genus_levels) predictions[[paste0("prob_genus_", nm)]] <- round6(genus_probs[, nm])
for (nm in species_levels) predictions[[paste0("prob_species_", nm)]] <- round6(posterior[, nm])
predictions <- predictions[order(predictions$row_id), ]

family_written <- as.matrix(predictions[, paste0("prob_family_", family_levels)])
genus_written <- as.matrix(predictions[, paste0("prob_genus_", genus_levels)])
species_written <- as.matrix(predictions[, paste0("prob_species_", species_levels)])
eval_with_pred <- merge(
  eval_raw[, c("row_id", "RecordID", "Family", "Genus", "Species")],
  predictions,
  by = c("row_id", "RecordID"),
  sort = FALSE
)
eval_with_pred <- eval_with_pred[order(eval_with_pred$row_id), ]

family_merged <- as.matrix(eval_with_pred[, paste0("prob_family_", family_levels)])
genus_merged <- as.matrix(eval_with_pred[, paste0("prob_genus_", genus_levels)])
species_merged <- as.matrix(eval_with_pred[, paste0("prob_species_", species_levels)])
family_merged_norm <- family_merged / rowSums(family_merged)
genus_merged_norm <- genus_merged / rowSums(genus_merged)
species_merged_norm <- species_merged / rowSums(species_merged)

record_report <- do.call(rbind, lapply(sort(unique(eval_with_pred$RecordID)), function(rid) {
  part <- eval_with_pred[eval_with_pred$RecordID == rid, , drop = FALSE]
  row_prob_species <- colMeans(as.matrix(part[, paste0("prob_species_", species_levels), drop = FALSE]))
  row_prob_genus <- colMeans(as.matrix(part[, paste0("prob_genus_", genus_levels), drop = FALSE]))
  row_prob_family <- colMeans(as.matrix(part[, paste0("prob_family_", family_levels), drop = FALSE]))
  data.frame(
    RecordID = as.integer(rid),
    n_rows = as.integer(nrow(part)),
    obs_family = as.character(unique(part$Family)),
    obs_genus = as.character(unique(part$Genus)),
    obs_species = as.character(unique(part$Species)),
    pred_family = family_levels[max.col(matrix(row_prob_family, nrow = 1), ties.method = "first")],
    pred_genus = genus_levels[max.col(matrix(row_prob_genus, nrow = 1), ties.method = "first")],
    pred_species = species_levels[max.col(matrix(row_prob_species, nrow = 1), ties.method = "first")],
    record_abstain = as.integer(max(row_prob_species) < 0.55),
    mean_pred_family_prob = round6(max(row_prob_family)),
    mean_pred_genus_prob = round6(max(row_prob_genus)),
    mean_pred_species_prob = round6(max(row_prob_species)),
    stringsAsFactors = FALSE
  )
}))
record_report <- record_report[order(record_report$RecordID), ]

write.csv(predictions, file.path(OUTPUT_PATH, "predictions.csv"), row.names = FALSE, quote = FALSE)
write.csv(record_report, file.path(OUTPUT_PATH, "record_report.csv"), row.names = FALSE, quote = FALSE)

predictions_disk <- read.csv(
  file.path(OUTPUT_PATH, "predictions.csv"),
  check.names = FALSE,
  stringsAsFactors = FALSE
)
disk_eval_with_pred <- merge(
  eval_raw[, c("row_id", "RecordID", "Family", "Genus", "Species")],
  predictions_disk,
  by = c("row_id", "RecordID"),
  sort = FALSE
)
disk_eval_with_pred <- disk_eval_with_pred[order(disk_eval_with_pred$row_id), ]
family_disk <- as.matrix(disk_eval_with_pred[, paste0("prob_family_", family_levels)])
genus_disk <- as.matrix(disk_eval_with_pred[, paste0("prob_genus_", genus_levels)])
species_disk <- as.matrix(disk_eval_with_pred[, paste0("prob_species_", species_levels)])
family_disk_norm <- family_disk / rowSums(family_disk)
genus_disk_norm <- genus_disk / rowSums(genus_disk)
species_disk_norm <- species_disk / rowSums(species_disk)

sklearn_logloss <- function(levels, prefix, truth_col) {
  source_path <- normalizePath(file.path(DATA_PATH, "Frogs_MFCCs.csv"), mustWork = TRUE)
  pred_path <- normalizePath(file.path(OUTPUT_PATH, "predictions.csv"), mustWork = TRUE)
  python_exe <- "/usr/bin/python3"
  if (!file.exists(python_exe)) {
    python_exe <- Sys.which("python3")
  }
  if (is.null(python_exe) || !nzchar(python_exe)) {
    stop("python executable not found; install python3")
  }
  python_code <- paste(
    "import json",
    "import numpy as np",
    "import pandas as pd",
    "from sklearn.metrics import log_loss",
    sprintf("src = pd.read_csv(%s)", jsonlite::toJSON(source_path, auto_unbox = TRUE)),
    "src.columns = [c.replace(' ', '') for c in src.columns]",
    "src = src.rename(columns={f'MFCCs_{i}': f'MFCC_{i}' for i in range(1, 23)})",
    "if 'row_id' in src.columns:",
    "    src['row_id'] = src['row_id'].astype(int)",
    "else:",
    "    src['row_id'] = np.arange(len(src), dtype=int)",
    "truth = src[src['row_id'] % 5 == 0].sort_values('row_id').reset_index(drop=True)",
    sprintf("pred = pd.read_csv(%s).sort_values('row_id').reset_index(drop=True)", jsonlite::toJSON(pred_path, auto_unbox = TRUE)),
    sprintf("labels = %s", jsonlite::toJSON(levels, auto_unbox = TRUE)),
    sprintf("cols = [c for c in pred.columns if c.startswith('%s')]", prefix),
    "prob = pred[cols].to_numpy(dtype=float)",
    "prob = prob / prob.sum(axis=1, keepdims=True)",
    sprintf("print(log_loss(truth['%s'].astype(str), prob, labels=labels))", truth_col),
    sep = "\n"
  )
  script_path <- tempfile(fileext = ".py")
  writeLines(python_code, script_path)
  on.exit(unlink(script_path), add = TRUE)
  as.numeric(system2(python_exe, script_path, stdout = TRUE))
}

y_species <- as.character(disk_eval_with_pred$Species)
y_genus <- as.character(disk_eval_with_pred$Genus)
y_family <- as.character(disk_eval_with_pred$Family)
pred_species_merged_idx <- max.col(species_disk, ties.method = "first")
pred_genus_merged_idx <- max.col(genus_disk, ties.method = "first")
pred_family_merged_idx <- max.col(family_disk, ties.method = "first")

metrics <- list(
  n_train_rows = as.integer(nrow(train_raw)),
  n_eval_rows = as.integer(nrow(eval_raw)),
  n_train_records = as.integer(length(unique(train_raw$RecordID))),
  n_eval_records = as.integer(length(unique(eval_raw$RecordID))),
  species_log_loss = round6(sklearn_logloss(species_levels, "prob_species_", "Species")),
  genus_log_loss = round6(sklearn_logloss(genus_levels, "prob_genus_", "Genus")),
  family_log_loss = round6(sklearn_logloss(family_levels, "prob_family_", "Family")),
  species_brier = round6(brier_multiclass(y_species, species_disk, species_levels)),
  genus_brier = round6(brier_multiclass(y_genus, genus_disk, genus_levels)),
  family_brier = round6(brier_multiclass(y_family, family_disk, family_levels)),
  species_ece_10bin = round6(ece(as.integer(y_species == species_levels[pred_species_merged_idx]), apply(species_disk_norm, 1, max), 10L)),
  genus_ece_10bin = round6(ece(as.integer(y_genus == genus_levels[pred_genus_merged_idx]), apply(genus_disk_norm, 1, max), 10L)),
  family_ece_10bin = round6(ece(as.integer(y_family == family_levels[pred_family_merged_idx]), apply(family_disk_norm, 1, max), 10L)),
  family_residual_max = round6(max(abs(family_disk - (species_disk %*% species_to_family)))),
  genus_residual_max = round6(max(abs(genus_disk - (species_disk %*% species_to_genus)))),
  row_abstain_rate = round6(mean(predictions$pred_abstain)),
  record_abstain_rate = round6(mean(record_report$record_abstain))
)

write_json(metrics, file.path(OUTPUT_PATH, "taxonomy_audit.json"), auto_unbox = TRUE, pretty = TRUE, digits = 8)
