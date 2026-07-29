# Studying an opening

Each opening is studied on its own. All five quantities below concern the
opening's own position (its heaps in canonical form) and the play that follows
from it. "Size" always means the number of counters in the opening, which never
changes during play.

- **redeals_to_endgame** — the number of redeals needed, starting from the
  opening, before the table first shows a position that belongs to the opening's
  endgame. If the opening's own position is already part of an endgame, this is
  `0`.

- **endgame_length** — the number of distinct positions in the endgame that play
  from this opening eventually falls into. It is `1` when the opening settles onto
  a single layout that redeals into itself, and greater than `1` when the endgame
  is a longer recurring run.

- **endgame** — the endgame that play from this opening falls into, written as an
  ordered list of positions exactly as described in `positions-and-order.md`
  (starting from the smallest position in the run). Two openings of the same size
  may fall into the same endgame or into different ones.

- **arrivals** — the number of distinct positions of the same size that redeal
  directly into the opening's position. That is, how many different layouts of the
  same number of counters would, after a single redeal, show exactly this
  opening's position. A position may have several such predecessors, exactly one,
  or none.

- **reachable** — whether the opening's position can be produced by a redeal from
  any position of the same size at all; equivalently, whether **arrivals** is
  greater than zero. Some layouts can only ever be set out by hand and are never
  the result of a redeal.
