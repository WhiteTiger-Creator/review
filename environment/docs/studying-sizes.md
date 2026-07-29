# Studying a size

Besides the individual openings, the game is studied one **size** at a time. The
sizes studied are exactly the distinct counter totals that appear among the
openings: if some opening has ten counters, then ten counters is one of the sizes
studied, and it is studied once no matter how many openings share that total.

A single size covers **every** position with that many counters — every way that
many counters can be laid into heaps, regardless of which openings happen to use
it. For each size the following are reported.

- **positions** — the number of distinct positions of that size, i.e. the number
  of different ways that many counters can be arranged into heaps (heap order
  ignored, every heap holding at least one counter).

- **unreachable_positions** — how many positions of that size are never the result
  of a redeal; that is, how many positions of that size have no predecessor of the
  same size. These are exactly the positions for which **reachable** would be
  false.

- **longest_settling** — the greatest **redeals_to_endgame** taken over all
  positions of that size: the largest number of redeals any layout of that size
  needs before first reaching its endgame.

- **endgames** — every distinct endgame that occurs for that size. Different
  openings of the same size can drain into different recurring runs, and each such
  run is listed once here. Each endgame is written as an ordered list of positions
  (as in `positions-and-order.md`) together with its length. The endgames of a
  size are listed in order of their smallest position.
