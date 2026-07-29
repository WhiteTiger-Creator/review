# Hop map

Principal pad codes and open hop tables drive the walk that yields each
row hop_key. Mesh obligation requires every emitted hop_key to match that
live walk for the row pad and the bound pipeline seed.

Pad cycles follow.

- pad 1 starts at a0 and walks a0-a1-a2-a0
- pad 2 starts at b0 and walks b0-b1-b2-b0
- pad 3 starts at c0 and walks c0-c1-c2-c0
- pad 4 starts at d0 and walks d0-d1-d2-d3-d0

The annex publishes at least 2 pad-4 claim entries so the longer cycle is
exercised more than once. Walk the full published pad cycle until the
start label repeats, mixing every visited label including the return. Do
not hardcode a three-step walk; pad four has a longer cycle. Initialize h as W xor
(P times 0xC2B2AE3D). Mix each label character via (h xor c) times
0x100000001B3. hop_key is the 16 lowercase hex digits of h.

The pipeline constant is 0x4D31A7. Before any walk, bind that constant to
the annex blob magic (little-endian u32 at the head of
`/app/data/annex31/slot_blob.bin`) as S set to pipe xor (magic and
0xffffff), using the low twenty-four bits of magic (not a narrower
sixteen-bit mask). Train-arm walks use W equal to S. Hold-arm walks use W
equal to S xor (((E + (pad times 3)) xor (pad left-shift 2)) and 0xff),
where E is the annex manifest epoch and pad is the row pad code. Parentheses
matter: add pad times 3 to E first, then xor with (pad left-shift 2), then
mask to eight bits. Do not use (E + pad) and 0xff, do not use a product
(E times pad) mix, and do not use a flat (E and 0xff) mix. After E moves,
hold hop_key values must follow that latch on the next regeneration. Train
hop_keys must keep the unbound S walk.

Operator side caches under `/app/output/side` can look locally green while
still encoding a short walk; graded regeneration must use the live cycle.
A two-label short walk must not match graded hop_key values. Cache lines
may carry a seed fingerprint; a mismatched fingerprint must not freeze
graded hops.
