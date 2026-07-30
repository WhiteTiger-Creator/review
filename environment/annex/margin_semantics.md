# Save-state and scoring semantics

Numeric pairing, binding, seal, and scoring residual definitions for this engine
are specified in `/app/annex/margin_contract.inc`. Long-form obligation text is under
`/app/annex/slice_137.txt`.

Seal digests use SHA-256 over payload material with a context tag. Closed corpora
rows record nest depth, boost, gap residuals, and suite assignment (suite_a,
suite_b, or suite_c). Closed instances carry fuzz margin vectors.

Schedule pairing defines slot_score and boosted_score. Gap residuals define
expected_gap. Closed corpora are structured so that slot score pairing and gap
residuals align when implemented according to specification.

Dossier outputs include dossier_rows, trace_span_digest (the SHA-256 digest of
sorted seal hex values), and obligation_coverage.

Every dossier row identifies its record via instance_id. Closed corpora copy their
instance_id. Arm-omit corpora publish case_id as the case key, which emit stores
under instance_id on the row. Row payload contains the sealed UTF-8 bytes with
ctx_tag. Additional fields include seal_hex, fragment_line, slot_score,
boosted_score, nest_depth, graph, and edge_arms. For closed instances the arm set
contains core, west, and east. For arm-omit cases, the omitted arm must appear inside
edge_arms.

The journal epoch records the emit watermark from `/app/runtime/journal/epoch.stamp`.
Shard files persist under `/app/runtime/journal/`. Transcript recovery digest
represents the SHA-256 hash over sorted closed-instance replay digests.

## Transcript polarity and membership

When a dossier is verified, transcript fields verify_clean, all_margins_clean, and
coverage_ok are set to true for closed instances.

Dossier membership cardinality equals the combined count of closed corpus instances
and arm-omit corpus instances. Context tags follow the format graph:nest_depth
(using a colon separator). Logical graph structures in closed corpora include ns7,
ns9, and related topology nodes.
