#!/usr/bin/env bash
set -u

cat > /app/solve.R <<'RSCRIPT'
args <- commandArgs(trailingOnly = TRUE)
data_dir <- args[1]
out_path <- args[2]

planets <- read.csv(file.path(data_dir, "planets.csv"), stringsAsFactors = FALSE)
cfgs <- read.csv(file.path(data_dir, "configurations.csv"), stringsAsFactors = FALSE)
qtab <- read.csv(file.path(data_dir, "queries.csv"), stringsAsFactors = FALSE)

kfun <- function(a, b, sv, ell) sv * exp(-0.5 * (outer(a, b, "-") / ell)^2)

gwarp <- function(name, y, lam) {
  if (name == "identity") return(list(z = y, gp = rep(1, length(y))))
  if (name == "log") return(list(z = log(y), gp = 1 / y))
  list(z = (y^lam - 1) / lam, gp = y^(lam - 1))
}

ginv <- function(name, u, lam) {
  if (name == "identity") return(u)
  if (name == "log") return(exp(u))
  base <- lam * u + 1
  out <- rep(NA_real_, length(u))
  ok <- base > 0
  out[ok] <- base[ok]^(1 / lam)
  out
}

fmtnum <- function(v) if (is.na(v) || !is.finite(v)) "null" else sprintf("%.17g", v)
fmtarr <- function(v) paste0("[", paste(vapply(v, fmtnum, ""), collapse = ","), "]")
fmtmat <- function(m) paste0("[", paste(apply(m, 1, fmtarr), collapse = ","), "]")

cfgjson <- character(nrow(cfgs))

for (ci in seq_len(nrow(cfgs))) {
  cf <- cfgs[ci, ]
  tr <- planets[planets$facility == cf$facility, ]
  tr <- tr[seq_len(cf$n_train), ]
  x <- tr$log_mass_earth
  y <- tr$radius_earth
  sg <- tr$radius_sigma_earth
  n <- length(x)

  qq <- qtab[qtab$config_id == cf$config_id, ]
  qq <- qq[order(qq$query_index), ]
  xq <- qq$log_mass_earth

  warps <- strsplit(cf$warp_catalogue, ";")[[1]]
  lam <- cf$boxcox_lambda
  zlo <- qnorm(cf$quantile_low)
  zhi <- qnorm(cf$quantile_high)

  K <- kfun(x, x, cf$signal_variance, cf$lengthscale)
  Kq <- kfun(x, xq, cf$signal_variance, cf$lengthscale)
  Kqq <- kfun(xq, xq, cf$signal_variance, cf$lengthscale)

  ev <- numeric(length(warps))
  blocks <- character(length(warps))

  for (wi in seq_along(warps)) {
    w <- warps[wi]
    g <- gwarp(w, y, lam)
    s <- sg * g$gp
    cc <- mean(g$z)
    zt <- g$z - cc

    A <- K + diag(s^2, n) + cf$jitter * diag(n)
    R <- chol(A)
    alpha <- backsolve(R, forwardsolve(t(R), zt))
    logdet <- 2 * sum(log(diag(R)))

    ev[wi] <- -0.5 * sum(zt * alpha) - 0.5 * logdet -
      0.5 * n * log(2 * pi) + sum(log(g$gp))

    mu <- cc + as.vector(t(Kq) %*% alpha)
    V <- forwardsolve(t(R), Kq)
    Sig <- Kqq - t(V) %*% V
    dg <- diag(Sig)

    med <- ginv(w, mu, lam)
    ql <- ginv(w, mu + sqrt(dg) * zlo, lam)
    qh <- ginv(w, mu + sqrt(dg) * zhi, lam)

    if (w == "identity") {
      mdtxt <- fmtarr(mu)
    } else if (w == "log") {
      mdtxt <- fmtarr(exp(mu - dg))
    } else if (lam < 1) {
      mdtxt <- "null"
    } else {
      bb <- 1 + lam * mu
      mdtxt <- fmtarr(((bb + sqrt(bb^2 + 4 * lam * dg * (lam - 1))) / 2)^(1 / lam))
    }

    if (w == "identity") {
      mtxt <- fmtarr(mu)
      ctxt <- fmtmat(Sig)
    } else if (w == "log") {
      mtxt <- fmtarr(exp(mu + dg / 2))
      ctxt <- fmtmat(exp(outer(mu, mu, "+") + outer(dg, dg, "+") / 2) * expm1(Sig))
    } else {
      mtxt <- "null"
      ctxt <- "null"
    }

    blocks[wi] <- paste0(
      "{\"warp\":\"", w, "\",",
      "\"evidence\":", fmtnum(ev[wi]), ",",
      "\"median\":", fmtarr(med), ",",
      "\"mode\":", mdtxt, ",",
      "\"quantile_low\":", fmtarr(ql), ",",
      "\"quantile_high\":", fmtarr(qh), ",",
      "\"mean\":", mtxt, ",",
      "\"covariance\":", ctxt, "}"
    )
  }

  cand <- which(ev >= max(ev) - cf$tie_tolerance)
  sel <- warps[min(cand)]

  cfgjson[ci] <- paste0(
    "{\"config_id\":\"", cf$config_id, "\",",
    "\"selected_warp\":\"", sel, "\",",
    "\"warps\":[", paste(blocks, collapse = ","), "]}"
  )
}

writeLines(paste0("{\"configurations\":[", paste(cfgjson, collapse = ","), "]}"), out_path)
RSCRIPT

chmod 0644 /app/solve.R
