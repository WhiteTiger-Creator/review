# Glossary

- **Counter** — one of the identical tokens the solitaire is played with. The
  number of counters in play is fixed for a given opening.

- **Heap** — a group of one or more counters on the table. Heaps are told apart
  only by size; two heaps of equal size are interchangeable.

- **Position** — the multiset of heap sizes on the table at one instant, written
  in canonical (non-increasing) form. See `positions-and-order.md`.

- **Opening** — a starting position chosen by the player, supplied in the openings
  folder.

- **Redeal** — the single repeated move: one counter is lifted from every heap,
  emptied heaps vanish, and the lifted counters form one new heap. See
  `the-redeal.md`.

- **Endgame** — the closed run of positions that play eventually enters and then
  repeats forever. Its length is the number of distinct positions in the run; a
  length of `1` means a position that redeals into itself.

- **Predecessor** — a position that redeals directly into a given position. The
  count of a position's distinct predecessors is its **arrivals**.

- **Reachable** — describes a position that has at least one predecessor, i.e. one
  that some redeal can produce. A position with no predecessor can only be laid out
  by hand.

- **Size** — the number of counters in play; a whole game is studied one size at a
  time (`studying-sizes.md`).

- **Settling** — the passage from an opening to its endgame; the number of redeals
  it takes is that opening's **redeals_to_endgame**.
