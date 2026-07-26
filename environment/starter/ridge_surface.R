ridge_normal_equation <- function(x, y, lambda) {
  design <- cbind(intercept = 1, as.matrix(x))
  penalty <- diag(ncol(design))
  penalty[1, 1] <- 0
  solve(t(design) %*% design + lambda * penalty, t(design) %*% y)
}
