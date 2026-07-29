# The Redeal

The Redeal is a solitaire played with a handful of identical counters on a table.
The player first lays the counters out in one or more **heaps**; this starting
layout is called an **opening**. Only the sizes of the heaps matter — two heaps of
the same size are interchangeable, and the heaps are never labelled or ordered by
the player.

From then on the player makes the same move over and over. One move is called a
**redeal**:

1. Lift exactly one counter off the top of every heap that is currently on the
   table.
2. The heaps that held a single counter are now empty; they are gone.
3. Gather every counter that was just lifted into one hand and set the whole
   handful down as a **single new heap**. That new heap therefore holds exactly
   as many counters as there were heaps a moment ago (one counter came from each).

The total number of counters never changes during play; a redeal only moves
counters between heaps. Because the counters are limited, the layout on the table
must eventually repeat, and from then on the same layouts recur forever. That
recurring stretch of layouts is the game's **endgame** (see
`studying-openings.md`).

## A worked redeal

Take four counters laid out as two heaps of sizes 3 and 1.

- **Redeal 1.** One counter comes off each of the two heaps. The heap of 1 is now
  empty and disappears; the heap of 3 becomes a heap of 2. The two lifted
  counters form one new heap of size 2. The table now shows heaps 2 and 2.
- **Redeal 2.** One counter comes off each of the two heaps, leaving heaps 1 and
  1; the two lifted counters form a new heap of 2. The table now shows heaps 2,
  1, and 1.
- **Redeal 3.** One counter comes off each of the three heaps. Both heaps of 1
  disappear and the heap of 2 becomes a heap of 1; the three lifted counters form
  a new heap of 3. The table now shows heaps 3 and 1 again.

So this opening returns to its own layout after three redeals: its endgame is a
run of three recurring layouts, not a single settled one. Other openings do
settle onto one layout that redeals into itself unchanged. Both kinds of endgame
occur, and which one an opening reaches depends only on how many counters are in
play and how they start.
