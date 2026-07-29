# Treasure balance and threat curve

## Treasure bands

Ignore the start room. Partition remaining rooms:

- early: depth <= band_d1
- mid: band_d1 < depth <= band_d2
- late: depth > band_d2

For each non-empty band, density = total_gold_in_band / room_count_in_band must lie in `[band_lo[i], band_hi[i]]`.
Empty bands are exempt from density bounds (report density 0.0).

Total gold across all rooms (including start, usually 0) must lie in `[total_gold_lo, total_gold_hi]`.

## Threat curve

Walk the critical path in order. Let path index i act as route depth (start index 0).

- Maintain cumulative threat along the walk.
- After visiting each node, require `cum_threat <= threat_base + threat_slope * i`.
- Max single-room threat on the path must be <= `max_room_threat`.
