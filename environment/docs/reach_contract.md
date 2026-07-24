# Reach contract (solver-visible; restates instruction obligations)

## Shadow non-duplication
Once a permit path is shadow-dominated, reduction must keep any sole-witness permit entry for scenes in the baseline matrix.

## Mark authority
Durable bytes in `/app/data/seed_bundle.json` are authoritative for derived edges after partial recovery. Health probes are diagnostic only.

## Witness closure
Row witness fields and summary `lane_digest` must share the slow cross-format reducer. Fast catalog emit is not sufficient alone.

## Report fields
The report has rows and summary. Each row records field scenario_id, property span_rc, property hop_rc, property mark_rc, field drift_code, and field facet_hex (facet_hex means exactly 16 lowercase hexadecimal digits). The summary records field rows_total (rows_total counts the number of row objects), field consensus_status (consensus_status equals settled when coherent), field span_band (span_band means the ordered band label from the reducer header; it equals max abs drift_code across rows), field lane_digest, and field rule_count (rule_count means the size of the minimized active ruleset).

Mirror pairs are defined as lowerdir with lowerdir_echo, upper with upper_echo, and worker with worker_echo (lowerdir means the baseline scene lane; lowerdir_echo means its echo twin). The scene_ids schema lists every scenario_id that must appear as a row; those ids are defined as the lines in `/app/docs/scene_ids.txt`. mix_table means the step tuples under `/app/data/mix_table.toml`. build_hints means the argv notes under `/app/docs/build_hints.txt`.

## Lane material pairing
Each scene step tuple in mix_table drives lane material that feeds facet_hex. Echo twins must agree on facet_hex and the three closure fields when coherent. Baseline scenes with zero prev lineage must still produce lane material consistent with their echo twin, not a truncated fold.

## Pipeline obligations
Shadow-family lineage must fold consistently across the orchestrator bind path and worker reducers so facet material stays paired across echo twins. Durable mark bytes from seed_bundle must drive witness comparison; health probe readings alone must not satisfy mark closure. Row materialization must use the slow cross-format reducer shared with lane_digest, preferring durable marks when both are present. Per-flow combine callbacks must run in the order required for zone hops; reversing combine order yields premature drift (consensus_status not settled or non-zero drift_code).

## Coherence
When every row is coherent, drift_code is zero on every row, span_rc hop_rc and mark_rc are all true, facet_hex matches on each mirror pair, and consensus_status is settled. Incoherent runs break at least one of those conditions.

## Minimization
Shrink the active cover size while preserving baseline reachability for scene_ids plus extra_scenes. Prefer the lexicographically smallest lane_digest on ties. A settled minimized cover uses cover size 4 for the shipped scene set.
