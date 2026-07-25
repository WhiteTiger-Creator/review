# n3 trace schema

## storm_trace.json

| field | type | notes |
|-------|------|-------|
| format | string | value n3_v1 |
| grid | array | one object per profile bundle |

### grid row object

| field | type | notes |
|-------|------|-------|
| family | string | wave_alpha, wave_beta, wave_gamma, or wave_delta |
| lane_order | array of integers | ranked arm ids under the documented scoring contract |
| span_band | integer | aggregate hit tally across active include arms |
| span_digest | string | 64 lowercase hex chars |
| cold_digest | string | 64 lowercase hex chars |
| hot_digest | string | 64 lowercase hex chars |

## replay_audit.json

Written beside the trace on a successful grid-full run.

| field | type | notes |
|-------|------|-------|
| tip_gen | integer | active ledger tip generation |
| policy_gen | integer | selected overlay generation |
| policy_id | string | selected overlay policy_id |
| policy_path | string | selected overlay path under pack/ |
| ledger_fingerprint | string | sha256 hex of pack/ledger/waves.ndjson bytes |

## profile JSON (prf_w1.json through prf_w4.json)

| field | type | notes |
|-------|------|-------|
| family | string | bundle name |
| budget | integer | lane slot cap |
| band_limit | integer | maximum allowed span_band when converged |
| unit_slice | string | stem for /app/environment/pack/w8/<stem>.slice |
| incident_wave | string | stem for /app/environment/pack/incidents/<stem>.inc |
| permute | boolean | profile decode option |
| swap_masks | boolean | profile decode option |

## pack path manifest

| field | path | notes |
|-------|------|-------|
| sg_unit | /app/environment/pack/w8/sg.slice | pack field path for alpha-side unit slice |
| sd_unit | /app/environment/pack/w8/sd.slice | pack field path for delta-side unit slice |
| sg_incident | /app/environment/pack/incidents/sg.inc | pack field path for alpha-side incident wave |
| sd_incident | /app/environment/pack/incidents/sd.inc | pack field path for delta-side incident wave |
| token_seed | /app/environment/pack/seed/token_seed.bin | cold seed blob |
| anchor_staging | /app/environment/pack/seed/.anchor_staging | hot staging bytes |
| storm_gen | /app/environment/pack/seed/.storm_gen | decimal generation ledger |
| roll_scratch | /app/environment/pack/seed/.roll_scratch | bare-reset counter |
| waves_ledger | /app/environment/pack/ledger/waves.ndjson | restart wave records |
| policy_dir | /app/environment/pack/policy/ | overlay JSON files ov_gN.json |
| interim_smoke | /app/environment/pack/inter_m5.json | smoke-only decoy rows |

Preserve-anchor must leave the pack field blobs for sg_unit, sd_unit, sg_incident, and sd_incident unchanged on disk. Converged n3_v1 rows require the cold, hot, and span digest columns to match, and the generation ledger at `/app/environment/pack/seed/.storm_gen` must parse to decimal `0`. Staging that does not match the first eight bytes of `token_seed.bin` must prevent an n3_v1 report when the active tip selects a checkpoint whose staged prefix matches the cold seed.

## recovery scripts

| action | command |
|--------|---------|
| ops reset | `bash /app/environment/phase/rld_x2.sh` |
| restore with seed preservation | `bash /app/environment/phase/rld_x2.sh --preserve-anchor` |

Bare reset without preservation increments the roll counter, removes `.anchor_staging`, leaves `.storm_gen` non-zero, and mutates the wave ledger so tip selection and policy overlays become incoherent. After two bare resets without preserve, the grid must not emit n3_v1. Preserve-anchor copies `token_seed.bin` onto `.anchor_staging`, clears the roll counter, restores `.storm_gen` to `0`, and restores `waves.ndjson` from the clean checkpoint. Preserve-anchor must not mutate on-disk pack slices or incident waves listed above.

## wave_sched driver

Rebuild packages with `bash /app/environment/scripts/build_all.sh` before invoking

`/app/environment/bin/wave_sched --grid-full --out /app/output/storm_trace.json`

A successful run also writes `/app/output/replay_audit.json`. Row digests are lowercase hex of length 64. Workspace module checks via lib_probe must pass; driver output alone is insufficient. Probe binary builds under `/tests/lib_probe` and may leave its artifact at `/app/environment/.libprobe`.

## interim_smoke object

| field | type | notes |
|-------|------|-------|
| rows | array | smoke excerpt objects |
| rows[].family | string | bundle name |
| rows[].span_digest | string | 64 lowercase hex chars |
| rows[].span_band | integer | optional smoke tally |

## probe staging sample

Offline package probes may write the eight-byte staging sample `HOTSTG01` onto `.anchor_staging` to exercise hot-path tie-break ordering without matching the cold seed prefix.
