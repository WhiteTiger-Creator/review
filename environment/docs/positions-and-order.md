# Positions and their order

## A position

A **position** is what the table shows at one instant: the multiset of heap sizes.
Because the player never orders or labels heaps, a position is fully described by
listing its heap sizes with no regard to arrangement. Every heap has at least one
counter, so a position is a list of positive integers whose sum is the number of
counters in play.

Positions are always written in **canonical form**: the heap sizes in
non-increasing order (largest first). The layout with heaps of sizes 1, 3, and 2
is written `[3, 2, 1]`. An opening supplied in any order is understood as the same
position after sorting it this way, and every position that appears anywhere in a
report is written in canonical form.

## Ordering two positions

Positions are compared in the natural order on their canonical lists:

- Compare the first (largest) heap of each. The position with the smaller first
  heap comes first.
- On a tie, compare the next heap, and so on.
- If one list runs out while matching the other exactly so far, the shorter list
  comes first.

For example `[2, 1, 1]` comes before `[2, 2]` (equal first heap, then `1` is below
`2`), and `[2, 1]` comes before `[2, 1, 1]` (the shorter list is a prefix of the
longer). This is the ordering meant by "smallest" and by "sorted" everywhere in
these notes.

## Writing an endgame

An endgame is a closed run of positions, each redealing into the next and the last
redealing back to the first. It has no inherent starting point, so it is always
written starting from its **smallest** position (by the order above) and then
following redeals: the smallest position, then what it redeals into, then what
that redeals into, and so on, listing each position in the run exactly once. A
one-position endgame — a layout that redeals into itself — is written as a list
holding that single position.
