# Binding profiles

Pack and draw fixtures can override default barrier table parameters. The global row keys and cue hashes remain in `ref_q7_pack.json`.

## Pack margin bases

When a pack JSON defines `margin_bases` (integer array aligned to `ref_q7_pack.json` `row_keys` order), use those values as subtractive bases instead of `table_bases` from the reference table for that run.

Training pack `pack_t352.json` omits `margin_bases` and inherits reference bases.

## Draw wave scale

`k9_k7_pack.json` may define `wave_scale` as a map from wave id (`w0`, `w1`) to an integer multiplier. For stress runs, draw boosts use `floor(weight * wave_scale[wave])` instead of a fixed multiplier. When the active wave is absent from the map, use multiplier `3`.

Current fixture map:

| wave | multiplier |
|------|------------|
| w0   | 3          |
| w1   | 4          |

## Trace cluster order

Replay trace steps follow the barrier row key order by default. When held mode runs with `--permute` and the pack defines `permute_order`, trace framing must visit clusters in that permute order (one step per cluster, then a fork replay step on the last cluster in that order).
