Offline restart-storm budget tooling under `/app/environment` is drifting across ops cycles. Cold and hot digests diverge on graded bundles. Later profile rows inherit tallies from earlier ones. The wrong policy generation gets selected across ledger churn. A bare scrub leaves the ledger tip and overlay selection incoherent. n3_v1 stays unavailable until preserve-anchor recovery succeeds.

Repair the Go sources under `/app/environment`, rebuild with `bash /app/environment/scripts/build_all.sh`, then run `/app/environment/bin/wave_sched --grid-full --out /app/output/storm_trace.json`. A good run exits 0 and also writes `/app/output/replay_audit.json`.

Graded storm_trace format is n3_v1 with a grid of four families: wave_alpha, wave_beta, wave_gamma, and wave_delta. Each row carries family, lane_order, span_band, span_digest, cold_digest, and hot_digest. Digests are lowercase hex length 64. span_digest is the sealed hex digest over unit slice bytes, incident wave bytes, then for each active lane in lane_order that lane's mask as little-endian uint16 plus its arm-id slot byte, then the eight-byte staging prefix that fed ranking. cold_digest uses that same seal with the first eight bytes of `/app/environment/pack/seed/token_seed.bin` as the staging prefix. hot_digest uses that same seal with the staging bytes that actually fed lane ranking (gen-bound checkpoint `/app/environment/pack/checkpoints/stg_g{N}.bin` when present for selected overlay generation N, otherwise `/app/environment/pack/seed/.anchor_staging`). On a converged row the three digest columns match. span_band sums hit tallies across every active include arm after suppression, not only lane_order members.

Pack field paths that must survive preserve-anchor unchanged: `/app/environment/pack/w8/sg.slice`, `/app/environment/pack/w8/sd.slice`, `/app/environment/pack/incidents/sg.inc`, and `/app/environment/pack/incidents/sd.inc`.

Ledger tip is the largest gen among records in `/app/environment/pack/ledger/waves.ndjson` whose tomb field is false. Overlay selection loads `/app/environment/pack/policy/ov_g{N}.json` for that tip generation N. Overlay JSON carries gen, shadow_radius, and policy_id.

Shadow suppression uses the active overlay shadow_radius as distance threshold R. An include arm is suppressed when an exclude arm with non-zero shadow_link shares a mask bit and abs(id - link) meets or exceeds R. Exclude arms ordered by ascending Seq contribute suppression; include arms then form the active set. Graph readers observe the live overlay radius from the selected overlay or from a probe-installed temporary overlay.

Hit-cache identity covers family, selected overlay generation, shadow epoch, cell layout dimensions, and a signature over incident field bytes. After a successful tally the burst grid cache epoch matches its shadow epoch.

lane_order ranks by descending hit score, then by descending staged-anchor byte at arm_id modulo 8, then by ascending arm id, capped by the profile budget.

Emitting n3_v1 requires `/app/environment/pack/seed/.storm_gen` to parse as decimal 0. Cold and hot prefixes must agree for those digests to converge. A mismatched staging prefix (including the eight-byte sample HOTSTG01 or a one-byte flip versus the cold seed) blocks n3_v1 on the hot path when no matching gen-bound checkpoint binds the tip.

Ops recovery is `bash /app/environment/phase/rld_x2.sh`. A bare call with no flags increments the roll counter, drops staging, poisons storm_gen, and mutates the wave ledger. Two bare resets with no preserve leave the grid unable to emit n3_v1. Running that recovery script in preserve-anchor mode restores seed staging from token_seed.bin, clears the roll counter, clears storm_gen poison to 0, and restores ledger coherency from the clean checkpoint without mutating the pack field blobs listed above.

replay_audit must report tip_gen, policy_gen, policy_id, policy_path, and ledger_fingerprint (hex fingerprint of waves.ndjson bytes) consistent with the ledger tip and selected overlay.

Profile decode options permute and swap_masks reshape scoring arms, but digest prefixes still hash the on-disk unit slice and incident wave bytes. Interim rows in `/app/environment/pack/inter_m5.json` are smoke-only and must not match graded digests.

Hand-written JSON and static copies are not enough. Source under `/app/environment` has to be fixed. Rebuilt libraries must pass the offline package probes under `/tests/lib_probe`. Those probes install a temporary active overlay (generation, shadow radius, policy id, and path) through the policy package probe entry so shadow and ranking checks observe that radius without tip selection; that probe entry must remain available after source repairs. The driver must emit the contracts above.
