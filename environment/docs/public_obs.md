# Label-shift evaluation ledger

This is the model evaluation sheet for site-ranking inference under temporal cohort drift. Regenerated artifact lives at `/app/output/gate_ledger.json`.

## Top-level shape

The runs list is an ordered list of lane passes. Each entry reports lane, wave, and pack.
The waves list holds materialization summaries. Each entry reports name, win_ix, and digest_hex.
The rank_rows list holds one row per site side after feature cut and seal, with pair_id, side (a or b), win_lo, win_hi, site_nib (integer from zero through fifteen for the low nibble of the final coord byte), slot_ok (zero or one after seal), coord_hex (lowercase hex of packed hist bytes), and pack (source pack stem).
The shift_surfaces list is the chrono refresh trail, with pack, wave, hist_lo, hist_hi, delta (hist_hi minus hist_lo), seal_seq (one-based order), and freshness (integer counter).

## Shift predicates

Half-open windows keep a feature value inside the span from lo inclusive through hi exclusive using `/app/environment/data/window_meta.json`. A value equal to hi belongs to the next window, not the current one.

Site-pair equality requires that base id X and mirror id Xm (same feature values and hist bytes, swapped sides) produce matching rank_rows for X side a versus Xm side b on site_nib, slot_ok, win_lo, and win_hi after chrono, and likewise X side b versus Xm side a.

Twin layouts that only swap side labels without changing features must keep that equality.

Nibble round-trip requires site_nib to match the low nibble of the last packed coord byte (coord_hex decoded) and the low nibble of the last source pack hist byte.

Occlusion requires both sides to show slot_ok as zero when ascending and descending window scans disagree for a pair.

Idempotent chrono requires a second jar chrono without deleting the sheet to leave rank_rows cardinality and the multiset of pair_id, side, coord_hex unchanged (no duplicated rows).

Shift freshness for pack c8_ln_03 requires chrono shift_surfaces for that pack to form a chain where each next freshness advances by one relative to the previous contiguous step.

Packed bit requires slot_ok to follow the high-nibble bit of the first coord byte for chrono-wave rows when scans agree.

## Lane entry

Run `mvn -q -f /app/environment/pom.xml package` then
`java -jar /app/environment/target/marlin-engine.jar --lane chrono`.
