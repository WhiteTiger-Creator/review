# The board, the instance, and how a Havannah position is settled

Everything the verdict in `src/judge.f90` depends on is written down here: what
the board looks like, how a point is named, and the exact wording of the three
shapes that end a game.

## The board and its points

The board is a hexagon, `N` points along each of its edges. A point carries a
pair `(q, r)`, and a third number `s` follows from them, `s = -q - r`, so the
three always add up to nothing. The pair is a point of the board exactly when
`max(|q|, |r|, |s|)` does not exceed `N - 1`. Stepping to a neighbour means
adding one of `(1,0)`, `(-1,0)`, `(0,1)`, `(0,-1)`, `(1,-1)`, `(-1,1)`; a step
that leaves the bound above lands nowhere, so a point has six neighbours inland
and fewer on the border.

There are six **corners**, and a point is one when, of its three numbers, one is
`N-1`, one is `-(N-1)`, and the last is `0`. There are also six **edges**, one
for each extreme value a number can take: the points with `q = N-1` make up one
edge, and so do `q = -(N-1)`, `r = N-1`, `r = -(N-1)`, `s = N-1`, and
`s = -(N-1)`. Two of a corner's numbers are extreme, so a corner sits on two
edges at once.

## What an instance says

An instance gives `size`, which is `N`; `player`, either `"A"` or `"B"`; and
`cells`, a map sending `"q,r"` to the stone standing on that point, again `"A"`
or `"B"`. Whatever is missing from the map is an empty point. Only `player` is
being asked about: has that side already finished one of the shapes below out of
stones of its own colour. Stones of the other colour and empty points never help
the count; they matter only by blocking the way, or by being what a loop has
managed to shut in.

## The three shapes

Work with groups: a group is a set of the asked-about player's stones that can
be walked between using the six neighbour steps, never leaving that colour. The
player has won the moment a single group answers to any one of the three.

A **bridge** is a group that holds two or more of the six corners.

A **fork** is a group that reaches three or more distinct edges. Corners are
kept out of this count entirely, contributing no edge at all, so only border
points that are not corners can raise the tally.

A **ring** is a group that has closed a loop around at least one point. That
shut-in point may be empty, may carry an enemy stone, or may even carry another
stone of the same colour. What settles it is that from that point there is no
route out to the rim of the hexagon that avoids stepping on the group's own
stones. Six stones placed around a single middle point are already a ring.

Several qualifying groups, or one group answering to more than one shape, still
add up to a plain win. Report a single shape, choosing `bridge` first, then
`fork`, and only failing both of those `ring`.
