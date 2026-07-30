# Margin and regret semantics (slice 137 companion)

All numeric checks use these formulas. Inputs come from SCL nest depth,
corpora instance fields, and the emit pipeline row fields.

## Slot score (schedule pairing)

For integer indices `left_idx` and `right_idx`, pairing uses a product
(not a sum of the shifted indices):

    slot_score = ((left_idx + 3) * (right_idx + 5) + 19) mod 97

When a schedule boost shift `boost` is applied for nested depth `d`:

    boosted_score = (slot_score + (d * 7) + boost) mod 97

Equivalently, if `flat` denotes the unboosted slot_score:

    boosted_score = (flat + nest_depth * 7 + boost) % 97

Schedule scores must be computed from the pairing formula above. Do not
substitute gap residuals for `boosted_score`. An additive rewrite such as
`(left_idx + 3) + (right_idx + 5) + 19` is not the pairing contract.

## Gap residual (corpus constraint)

Closed corpora also publish independent residual fields `gap_a` and `gap_b`.
For nest depth `d`:

    expected_gap = (gap_a * 3 + gap_b * 5 + nest_depth * 7) mod 97

Every closed instance is constructed so that the pairing-derived
`boosted_score` equals `expected_gap`. That equality is a corpus property
agents must preserve by implementing the pairing formula correctly, not by
copying `expected_gap` into the dossier row.

## Fragment line (formal binding)

For graph id `G` and nest depth `d`:

    continuity = (FNV-1a32(G) + d * 13) mod 100000
    fragment_line = "G:" + G + "|D:" + decimal(d) + "|C:N" + decimal(continuity)

Continuity tags (`C:N...`) must appear on every dossier row that covers
a nested logical-node instance.

## Seal digest

Given UTF-8 row payload bytes `row_blob` and context tag `ctx_tag`:

    material = row_blob || 0x1F || UTF-8(ctx_tag)
    seal_hex = lowercase hex of sha256(material)

The digest algorithm is sha256 (not md5 or sha1). Sealing must be
deterministic: identical inputs yield identical digests across idempotent
reruns and across adversarial permutation of emit order. Digests are
per-row: two rows that share a ctx_tag but differ in row_payload must
produce distinct seal_hex values. Do not reuse a digest across rows.

Context tags for closed and arm-omit rows use the form
`graph + ":" + decimal(nest_depth)`.

## Dossier top-level fields

Field dossier_rows means the array of per-instance emit rows. Field
trace_span_digest means lowercase hex SHA-256 of the JSON array encoding of
`seal_hex` values sorted lexicographically (not raw string concatenation).
Field obligation_coverage means the list of obligation IDs covered by the emit.

Closed corpora rows also carry a suite label (suite_a, suite_b, or suite_c)
naming which fixture suite the instance belongs to. Emit does not need to
echo suite into dossier rows; the label is a corpus identity used when
checking cross-suite coverage.

Every dossier row uses the JSON field name `instance_id`. Closed corpora copy
their `instance_id` key. Arm-omit corpora under
`/app/corpora/arm_omit_cases.jsonl` publish `case_id` as the case key; emit
still writes that value into row field `instance_id` (do not rename the row
field to `case_id`). Each row also includes row_payload (UTF-8 emit material),
ctx_tag, seal_hex, fragment_line, slot_score, boosted_score, nest_depth, graph,
and edge_arms. Field row_payload means the UTF-8 bytes sealed with ctx_tag.
Row payload material is
`instance_id + "|" + decimal(boosted_score) + "|" + fragment_line`.
For arm-omit cases, the omitted_arm value must appear inside edge_arms.

## Fuzz margin vector (closed instances)

The independent fuzz probe checks three margins per closed instance. Let
`slot_score`, `boosted_score`, and `nest_depth` come from the dossier row, and
let `boost`, `gap_a`, `gap_b` come from the closed corpus entry:

    expected_gap = (gap_a * 3 + gap_b * 5 + nest_depth * 7) mod 97
    schedule_boosted means the annex schedule shift
    schedule_boosted = (slot_score + nest_depth * 7 + boost) mod 97

    margin_0 = float(boosted_score - expected_gap)
    margin_1 = float(boosted_score - schedule_boosted)
    margin_2 = 0.0 if fragment continuity and seal digest both match formulas else -1.0

A violation is any component with absolute value greater than 1e-9 when
the instance is marked closed. Zero violations are required for OBL-11.

Because closed corpora satisfy `expected_gap == pairing-derived boosted_score`,
margin_0 and margin_1 are simultaneously zero only when the emitter computes
pairing, depth shift, and boost correctly and reports a coherent
`slot_score`/`boosted_score` pair. Writing `boosted_score = expected_gap`
while leaving `slot_score` inconsistent leaves margin_1 nonzero.

## Obligation coverage

Dossier `obligation_coverage` must include at least:
`OBL-11`, `OBL-11a`, `OBL-11b`, `OBL-11c` when the corresponding corpora
are present under `/app/corpora`.

## Trace and replay digests

`trace_span_digest` is lowercase hex SHA-256 over the canonical JSON array
encoding of dossier row `seal_hex` values sorted lexicographically. Use a
JSON array string as the hash input (for example via a JSON dump of the
sorted string list). Do not hash a bare concatenation of hex strings.

Per-instance `replay_digest` is lowercase hex SHA-256 over:
`instance_id || "|" || seal_hex || "|" || fragment_line`.

Transcript field `recovery_digest` is lowercase hex SHA-256 over the JSON
array encoding of all closed-instance `replay_digest` values sorted
lexicographically (same array-encoding rule as `trace_span_digest`).

## Journal shards and epoch merge

Emit must durable-journal every built row under `/app/runtime/journal/` before
the public dossier is finalized:

- `suite_a.jsonl`, `suite_b.jsonl`, `suite_c.jsonl` for closed instances
  routed by their corpus `suite` label
- `arm_omit.jsonl` for arm-omit cases

Each journal line is the row JSON plus an integer field `epoch` equal to the
current watermark written at `/app/runtime/journal/epoch.stamp`. The stamp
increments once per successful emit start. Shard files are durable across
emits: prior-epoch lines remain on disk and accumulate. Emit appends the
new epoch's lines; it must not rely on wiping shards to look correct.

Dossier assembly merges journal lines whose `epoch` equals the current
watermark from all four shard files. Stale lines from older epochs must not
appear in `dossier_rows`, even when they share an `instance_id` with a newer
line and appear earlier in the shard. Closed rows must land in the suite
shard named by their corpus `suite` label; arm-omit rows must land in
`arm_omit.jsonl`. Arm-omit rows must survive the merge. Row field
`edge_arms` must survive journaling (do not drop it when writing shards).

Top-level dossier fields:

- `journal_epoch`: the watermark used for this emit
- `shard_manifest`: the list `["suite_a","suite_b","suite_c","arm_omit"]`

Routing-only keys such as `suite` and `epoch` may be stripped from public
`dossier_rows` after merge. Seal caches must not reuse a digest across
distinct payloads that share a `ctx_tag`, and must not retain entries across
epoch advances.
