# Cartograph contract

Deterministic map generation from `(campaign, seed)`:

1. RNG is xorshift64*. Initialize state to `seed | 1` (never zero).
2. Each draw updates state then yields the new state as a u64 sample.
3. Attempt to place `room_target` axis-aligned rooms on a `width` x `height` board.
   - Room width/height = `3 + (sample % 3)` each.
   - Top-left x = `1 + (sample % max(1, width - w - 1))`, same for y.
   - Reject overlaps that violate a 1-tile gap (rooms may not touch even at corners of the expanded bbox).
   - Cap placement attempts at 5000.
4. Connect rooms: edges `(i-1, i)` for i in 1..n, plus `max(1, n/3)` extra random edges.
5. BFS depth from room 0. Unreachable rooms get depth 999.
6. Start room is 0. Exit room is the reachable room with maximum depth (tie: lowest id).
7. Place `chest_count` chests on non-start rooms: gold = `10 + (sample % 40) + depth*5` added to that room.
8. Place `monster_count` monsters on non-start rooms: threat = `3 + (sample % 8) + depth*2` added to that room.

Rooms and undirected edges form the playfield graph used by later contracts.
