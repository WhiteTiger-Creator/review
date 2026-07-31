suppressPackageStartupMessages(library(nnet))

data_dir <- Sys.getenv("WL_DATA_DIR", "/app/data")
output_path <- Sys.getenv("WL_OUTPUT_PATH", "/app/predictions.csv")

features <- read.csv(file.path(data_dir, "features.csv"), stringsAsFactors = FALSE, check.names = FALSE)
anchors <- read.csv(file.path(data_dir, "anchors.csv"), stringsAsFactors = FALSE)
annotations <- read.csv(file.path(data_dir, "annotations.csv"), stringsAsFactors = FALSE)
vocabularies <- read.csv(file.path(data_dir, "vocabularies.csv"), stringsAsFactors = FALSE)
classes <- read.csv(file.path(data_dir, "classes.csv"), stringsAsFactors = FALSE)$canonical_class

permutations <- function(values) {
  if (length(values) == 1) {
    return(matrix(values, nrow = 1))
  }
  blocks <- lapply(seq_along(values), function(i) {
    rest <- permutations(values[-i])
    cbind(values[i], rest)
  })
  do.call(rbind, blocks)
}

anchor_lookup <- setNames(anchors$canonical_class, anchors$observation_id)
mapped_rows <- vector("list", 0)
worker_quality <- numeric(0)

for (worker in unique(vocabularies$worker_id)) {
  symbols <- sort(vocabularies$local_symbol[vocabularies$worker_id == worker])
  worker_rows <- annotations[annotations$worker_id == worker, , drop = FALSE]
  calibration <- worker_rows[worker_rows$observation_id %in% anchors$observation_id, , drop = FALSE]
  candidate_permutations <- permutations(classes)
  scores <- numeric(nrow(candidate_permutations))
  for (j in seq_len(nrow(candidate_permutations))) {
    mapping <- setNames(candidate_permutations[j, ], symbols)
    scores[j] <- sum(mapping[calibration$local_symbol] == anchor_lookup[calibration$observation_id])
  }
  best <- which.max(scores)
  mapping <- setNames(candidate_permutations[best, ], symbols)
  worker_rows$canonical_class <- unname(mapping[worker_rows$local_symbol])
  correct <- sum(mapping[calibration$local_symbol] == anchor_lookup[calibration$observation_id])
  quality <- (correct + 2) / (nrow(calibration) + 4)
  quality <- min(max(quality, 1 / length(classes) + 0.01), 0.97)
  worker_quality[worker] <- quality
  mapped_rows[[length(mapped_rows) + 1]] <- worker_rows
}

mapped <- do.call(rbind, mapped_rows)
train <- features[features$partition == "train", , drop = FALSE]
query <- features[features$partition == "query", , drop = FALSE]
scores <- matrix(0, nrow = nrow(train), ncol = length(classes), dimnames = list(train$observation_id, classes))

for (j in seq_len(nrow(mapped))) {
  obs <- mapped$observation_id[j]
  if (!(obs %in% rownames(scores))) {
    next
  }
  worker <- mapped$worker_id[j]
  label <- mapped$canonical_class[j]
  quality <- worker_quality[worker]
  scores[obs, label] <- scores[obs, label] + log((quality + 1e-6) / ((1 - quality) / (length(classes) - 1) + 1e-6))
}

pseudo <- classes[max.col(scores, ties.method = "first")]
names(pseudo) <- rownames(scores)
pseudo[anchors$observation_id] <- anchors$canonical_class
confidence <- apply(scores, 1, function(row) {
  shifted <- exp(row - max(row))
  max(shifted / sum(shifted))
})
weights <- 0.5 + confidence
weights[anchors$observation_id] <- 3

feature_names <- paste0("f", seq_len(10))
augment <- function(frame) {
  for (feature in feature_names) {
    frame[[paste0(feature, "_sq")]] <- frame[[feature]]^2
  }
  frame$f2_f3 <- frame$f2 * frame$f3
  frame$f5_f6 <- frame$f5 * frame$f6
  frame$f8_f10 <- frame$f8 * frame$f10
  frame
}
model_frame <- augment(train[, feature_names, drop = FALSE])
model_frame$copyist <- factor(pseudo[train$observation_id], levels = classes)
fit <- multinom(copyist ~ ., data = model_frame, weights = weights[train$observation_id], decay = 0.02, maxit = 1200, trace = FALSE)
probabilities <- predict(fit, newdata = augment(query[, feature_names, drop = FALSE]), type = "probs")
probabilities <- probabilities[, classes, drop = FALSE]
probabilities <- probabilities^(1 / 3)
probabilities <- probabilities / rowSums(probabilities)
linear_frame <- train[, feature_names, drop = FALSE]
linear_frame$copyist <- factor(pseudo[train$observation_id], levels = classes)
linear_fit <- multinom(copyist ~ ., data = linear_frame, weights = weights[train$observation_id], decay = 0.02, maxit = 1200, trace = FALSE)
linear_probabilities <- predict(linear_fit, newdata = query[, feature_names, drop = FALSE], type = "probs")
linear_probabilities <- linear_probabilities[, classes, drop = FALSE]
linear_probabilities <- linear_probabilities^(1 / 1.25)
linear_probabilities <- linear_probabilities / rowSums(linear_probabilities)
probabilities <- 0.35 * probabilities + 0.65 * linear_probabilities
predicted <- classes[max.col(probabilities, ties.method = "first")]

result <- data.frame(
  observation_id = query$observation_id,
  predicted_class = predicted,
  probabilities,
  check.names = FALSE
)
names(result)[seq.int(3, 8)] <- paste0("prob_", classes)
write.csv(result, output_path, row.names = FALSE, quote = FALSE)
