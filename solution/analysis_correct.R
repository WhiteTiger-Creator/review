root <- Sys.getenv("ORBIT_EVIDENCE_DIR", unset = "/app/evidence")

fmt <- function(x) sprintf("%.6f", round(as.numeric(x) + 0, 6))
dot <- function(a, b) sum(a * b)
normv <- function(a) sqrt(sum(a * a))
policy_threshold <- function(tca, policy) {
  age_hours <- as.numeric(difftime(as.POSIXct(tca, tz="UTC"), as.POSIXct(policy$effective_tca, tz="UTC"), units="hours"))
  age_factor <- 1 + min(0.25, 0.015 * floor(age_hours / 6))
  as.numeric(policy$max_probability) * age_factor
}

risk <- function(row, policy) {
  r <- c(row$rx_km, row$ry_km, row$rz_km)
  v <- c(row$vx_km_s, row$vy_km_s, row$vz_km_s)
  w <- v / normv(v)
  ref <- if (abs(w[1]) < 0.8) c(1, 0, 0) else c(0, 1, 0)
  e1 <- ref - dot(ref, w) * w
  e1 <- e1 / normv(e1)
  e2 <- c(w[2] * e1[3] - w[3] * e1[2], w[3] * e1[1] - w[1] * e1[3], w[1] * e1[2] - w[2] * e1[1])
  scale <- as.numeric(policy$covariance_scale)
  hbr_km <- as.numeric(policy$hard_body_radius_m) / 1000
  floor_prob <- as.numeric(policy$probability_floor)
  cov <- scale * matrix(c(row$cxx, row$cxy, row$cxz, row$cxy, row$cyy, row$cyz, row$cxz, row$cyz, row$czz), 3, 3)
  b <- rbind(e1, e2)
  rp <- as.vector(b %*% r)
  cp <- b %*% cov %*% t(b)
  miss <- normv(rp)
  detv <- det(cp)
  if (detv <= 0) {
    sig <- ifelse(miss == 0, 0, Inf)
    prob <- min(1, ifelse(miss == 0, 1, 0) + floor_prob)
  } else {
    sig <- sqrt(as.numeric(t(rp) %*% solve(cp) %*% rp))
    inv_cp <- solve(cp)
    radial_nodes <- c(0.1127016654, 0.5, 0.8872983346)
    radial_weights <- c(5 / 18, 8 / 18, 5 / 18)
    angle_weight <- 2 * pi / 12
    disk_mass <- 0
    for (node_index in seq_along(radial_nodes)) {
      rho <- radial_nodes[node_index]
      radius_weight <- radial_weights[node_index]
      for (step in 0:11) {
        theta <- angle_weight * step
        point <- hbr_km * rho * c(cos(theta), sin(theta))
        delta <- point - rp
        q_point <- as.numeric(t(delta) %*% inv_cp %*% delta)
        density <- exp(-0.5 * max(q_point, 0)) / (2 * pi * sqrt(detv))
        disk_mass <- disk_mass + radius_weight * angle_weight * hbr_km * hbr_km * rho * density
      }
    }
    prob <- min(1, disk_mass + floor_prob)
  }
  c(miss, sig, prob)
}

enc <- read.csv(file.path(root, "orbits/encounters.csv"), stringsAsFactors = FALSE, check.names = FALSE)
pol <- read.csv(file.path(root, "policy/screening_policies.csv"), stringsAsFactors = FALSE, check.names = FALSE)
blk <- read.csv(file.path(root, "policy/maneuver_blackouts.csv"), stringsAsFactors = FALSE, check.names = FALSE)
num_cols <- c("rx_km","ry_km","rz_km","vx_km_s","vy_km_s","vz_km_s","cxx","cxy","cxz","cyy","cyz","czz")
for (col in num_cols) enc[[col]] <- as.numeric(enc[[col]])
for (col in c("max_miss_km","max_sigma_distance","max_probability","covariance_scale","hard_body_radius_m","probability_floor")) pol[[col]] <- as.numeric(pol[[col]])

rows <- list()
for (i in seq_len(nrow(enc))) {
  e <- enc[i, ]
  active <- pol[pol$status == "approved" & pol$quality_code == e$quality_code & pol$effective_tca <= e$tca, ]
  active <- active[order(active$effective_tca, active$revision_ts, active$policy_id), ]
  p <- active[nrow(active), ]
  b <- blk[blk$status == "approved" & blk$primary_id == e$primary_id & blk$start_tca <= e$tca & e$tca < blk$end_tca, ]
  blackout <- nrow(b) > 0
  vals <- risk(e, p)
  breach <- (!blackout) && vals[1] <= p$max_miss_km && vals[2] <= p$max_sigma_distance && vals[3] >= policy_threshold(e$tca, p)
  rows[[length(rows) + 1]] <- data.frame(
    encounter_id=e$encounter_id, primary_id=e$primary_id, secondary_id=e$secondary_id,
    projected_miss_km=fmt(vals[1]), sigma_distance=fmt(vals[2]), probability=fmt(vals[3]),
    blackout=ifelse(blackout, "TRUE", "FALSE"), decision=ifelse(breach, "BREACH", "CLEAR"),
    stringsAsFactors=FALSE
  )
}
out <- do.call(rbind, rows)
out <- out[order(out$encounter_id), ]
write.csv(out, "/app/encounter_risk_register.csv", row.names=FALSE, quote=FALSE)

out$prob_num <- as.numeric(out$probability)
out$miss_num <- as.numeric(out$projected_miss_km)
sum_rows <- list()
for (pid in sort(unique(out$primary_id))) {
  part <- out[out$primary_id == pid, ]
  sum_rows[[length(sum_rows)+1]] <- data.frame(
    primary_id=pid, total_encounters=nrow(part), breaches=sum(part$decision == "BREACH"),
    blackout_suppressed=sum(part$blackout == "TRUE"), max_probability=fmt(max(part$prob_num)),
    min_projected_miss_km=fmt(min(part$miss_num)), stringsAsFactors=FALSE
  )
}
summ <- do.call(rbind, sum_rows)
write.csv(summ, "/app/satellite_exposure_summary.csv", row.names=FALSE, quote=FALSE)
