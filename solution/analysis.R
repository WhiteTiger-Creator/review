FPR_BOUND <- 0.1
SENS_TARGET <- 0.95

dat <- read.csv("/app/data/sensors.csv", header = TRUE, stringsAsFactors = FALSE)
s <- as.numeric(dat$CO2)
y <- as.integer(dat$Occupancy)
P <- sum(y == 1L)
N <- sum(y == 0L)

r <- rank(s, ties.method = "average")
Rp <- sum(r[y == 1L])
auc <- (Rp - P * (P + 1) / 2) / (P * N)

thr <- sort(unique(s))
ord <- order(s, decreasing = TRUE)
ys <- y[ord]
ss <- s[ord]
csum_pos <- cumsum(ys == 1L)
csum_all <- seq_along(ys)

tp_at <- integer(length(thr))
fp_at <- integer(length(thr))
for (k in seq_along(thr)) {
  t <- thr[k]
  m <- sum(ss >= t)
  if (m == 0L) {
    tp_at[k] <- 0L
    fp_at[k] <- 0L
  } else {
    tp_at[k] <- csum_pos[m]
    fp_at[k] <- m - csum_pos[m]
  }
}
tn_at <- N - fp_at
fn_at <- P - tp_at
tpr_at <- tp_at / P
fpr_at <- fp_at / N

o <- order(thr)
thr_s <- thr[o]
f6 <- function(x) formatC(x, format = "f", digits = 6)
roc <- data.frame(threshold = f6(thr_s), tp = tp_at[o], fp = fp_at[o],
                  tn = tn_at[o], fn = fn_at[o],
                  tpr = f6(tpr_at[o]), fpr = f6(fpr_at[o]))
dir.create("/app/outputs", showWarnings = FALSE, recursive = TRUE)
write.csv(roc, "/app/outputs/roc_points.csv", row.names = FALSE, quote = FALSE)

od <- order(fpr_at, tpr_at)
fx <- c(0, fpr_at[od])
tx <- c(0, tpr_at[od])
keep <- fx <= FPR_BOUND + 1e-12
xf <- fx[keep]
yt <- tx[keep]
if (xf[length(xf)] < FPR_BOUND) {
  kk <- which(fx > FPR_BOUND)[1]
  x0 <- fx[kk - 1]
  x1 <- fx[kk]
  y0 <- tx[kk - 1]
  y1 <- tx[kk]
  yi <- y0 + (y1 - y0) * (FPR_BOUND - x0) / (x1 - x0)
  xf <- c(xf, FPR_BOUND)
  yt <- c(yt, yi)
}
raw <- sum(diff(xf) * (yt[-1] + yt[-length(yt)]) / 2)
pmin <- FPR_BOUND * FPR_BOUND / 2
pmax <- FPR_BOUND
pauc_std <- (1 + (raw - pmin) / (pmax - pmin)) / 2

sel <- which(tpr_at >= SENS_TARGET)
best <- sel[order(fpr_at[sel], -thr[sel])][1]
op_thr <- thr[best]
op_tp <- tp_at[best]
op_fp <- fp_at[best]
op_tn <- tn_at[best]
op_fn <- fn_at[best]
op_tpr <- op_tp / P
op_fpr <- op_fp / N
op_prec <- op_tp / (op_tp + op_fp)
op_f1 <- 2 * op_prec * op_tpr / (op_prec + op_tpr)

json <- paste0(
  '{\n  "n_pos": ', P,
  ',\n  "n_neg": ', N,
  ',\n  "auc": ', f6(auc),
  ',\n  "partial_auc_raw": ', f6(raw),
  ',\n  "partial_auc_standardized": ', f6(pauc_std),
  ',\n  "fpr_bound": ', f6(FPR_BOUND),
  ',\n  "sensitivity_target": ', f6(SENS_TARGET),
  ',\n  "operating_point": {',
  '\n    "threshold": ', f6(op_thr),
  ',\n    "tp": ', op_tp,
  ',\n    "fp": ', op_fp,
  ',\n    "tn": ', op_tn,
  ',\n    "fn": ', op_fn,
  ',\n    "tpr": ', f6(op_tpr),
  ',\n    "fpr": ', f6(op_fpr),
  ',\n    "precision": ', f6(op_prec),
  ',\n    "f1": ', f6(op_f1),
  '\n  }\n}\n')
writeLines(json, "/app/outputs/metrics.json")
