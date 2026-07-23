# Numeric policy for wind-farm icing site discharge

Scientific scoring for icing witness bundles: BER annex ingest, FTRL arm updates,
fold digests, certified envelope caps, and stress reachability containment.

## Annex ingest

Annex slices use BER-style TLV rows. Indefinite constructed sequences use tag `0x30`, length byte `0x80`, child rows, then terminator `0x00 0x00`. Each child row is a definite sequence: arm indicator (INTEGER), weight token (INTEGER), mode label (OCTET STRING).

Extract rows from indefinite wrappers before discharge. Presentation order in the slice file is not authoritative; canonize by `(arm_id, mode_digest)` ascending before any fold.

`mode_digest` is the first eight hex chars of SHA-256 over the mode octets.

## FTRL arm update

For schedule row with learning rate `eta` (column `eta`), update arm weight after reading annex weight token `w_tok`:

```
w_next = w_prev * exp(-eta * w_tok / 100.0)
```

Arm score for admission is `round(w_next / 10)` as an integer observation stored in `synth_obs`.

Admission label is `open` when the maximum arm score across the site is greater than or equal to the schedule `threshold`; otherwise `hold`.

## Output bundle fields

The `site_id` field must equal the site pack folder name. The `stress_id` field must equal the stress JSON filename stem under `_stress/`. The `fold_digest` field must follow the canon fold formula in this document. The `catalog_digest` field must cover every replayed lineage row.

`obligation_count` counts discharged rows whose `(arm_id, mode_digest)` pair is absent from the closed catalog replay set. Target is zero for site packs `s01`, `s02`, `s03`.

## Fold stability

`fold_digest` is lowercase hex of SHA-256 over UTF-8 lines `arm_id|mode_digest|weight_token` sorted by `(arm_id, mode_digest)`.

## Certified envelopes

`synth_obs` is a map of arm id strings to integer scores from the FTRL discharge. Each score must be less than or equal to `env_hi * 10` from the site schedule.

## Stress containment

For each stress record, `reach_obs` lists step probabilities. Sealed output stores `path_peak` as the maximum step probability. `path_peak` must be less than or equal to the site `env_hi` from schedule.

Stage-report scratch timelines are not certified and must not feed the seal.

## Catalog digest

After SQLite replay of migrations under `/app/environment/var/mig`, include every `arm_lineage` row in digest material. `catalog_digest` is lowercase hex SHA-256 over sorted `arm_id|mode_tag|lineage_seq|weight_base` lines after SQLite replay. Digest material may be checked with `sha256sum` over UTF-8 bytes.

## Output bundle

Write `/app/output/k_out.json` with `schema_version` 1, `sites` array, `stress` array, and `lineage_rows` array. Site objects carry `site_id`, `obligation_count`, `env_hi`, `synth_obs`, `fold_digest`, `catalog_digest`, `admission`, and `reach_obs` (empty array on sites). Stress objects carry `stress_id`, `site_id`, `path_peak`. Lineage rows mirror SQLite columns.
