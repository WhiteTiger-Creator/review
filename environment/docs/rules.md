# Rules in scope

This file is the complete and authoritative rule set for this project. It
restates the standard rules of Arimaa for a single position with a known side
to move. Everything written here is graded; nothing outside it is.

## Board and pieces

The board is eight by eight. Files run `a` to `h` from the left, ranks run `1`
to `8` from the bottom. Gold pieces are written in uppercase and Silver pieces
in lowercase. Each side has one elephant `E`, one camel `M`, two horses `H`,
two dogs `D`, two cats `C`, and up to eight rabbits `R`, though a position may
contain any subset of these. Strength ranks the piece types in that order:
the elephant is strongest, then camel, horse, dog, cat, and rabbit. Strength
comparisons are always strict; two pieces of the same type are never stronger
than one another.

Four squares are trap squares: `c3`, `f3`, `c6`, and `f6`.

Gold's home is the bottom of the board and Gold rabbits advance toward rank 8.
Silver's home is the top and Silver rabbits advance toward rank 1.

## Steps

A turn consists of one to four steps taken by the side to move. A step moves
one of the mover's own pieces to an orthogonally adjacent empty square. There
are no diagonal moves. A rabbit may never step toward its own home rank: a
Gold rabbit never steps from rank n to rank n minus one, and a Silver rabbit
never steps from rank n to rank n plus one. Rabbits may step sideways and
forward only. All other pieces step in any of the four directions.

## Pushing and pulling

A piece may dislodge a strictly weaker enemy piece from an adjacent square by
pushing or pulling it. Both actions consume two steps of the turn and must be
completed in full; they are only available when at least two steps remain.

To push, the acting piece chooses an adjacent enemy piece that is strictly
weaker and an empty square orthogonally adjacent to that enemy piece. The
enemy piece moves to the chosen empty square, and the acting piece then moves
into the square the enemy piece vacated.

To pull, the acting piece moves to an orthogonally adjacent empty square of
its own choice, and the chosen adjacent enemy piece, strictly weaker than the
acting piece, moves into the square the acting piece vacated.

A pushed or pulled piece may be moved in any direction; the rabbit
restriction applies only to a rabbit stepping on its own. Rabbits are the
weakest type and therefore can never push or pull anything. One action never
combines a push and a pull at the same time.

## Freezing

A piece is frozen when at least one orthogonally adjacent square holds a
strictly stronger enemy piece and no orthogonally adjacent square holds a
friendly piece. A frozen piece cannot step, push, or pull, but it can still
be pushed or pulled by the opponent, and it still guards traps as described
below. Freezing is evaluated on the current board at the moment a piece
would act, so a piece may be frozen at the start of a turn and act later in
the same turn, or the reverse, as pieces around it move.

## Traps

A piece standing on a trap square is captured and removed from the board
immediately unless at least one orthogonally adjacent square holds a friendly
piece. This condition is checked after every single piece movement, including
after each of the two movements inside a push or a pull. A capture can
therefore happen in the middle of a turn or in the middle of a push or pull:
a piece may step onto an unguarded trap and be lost at once, and a piece
standing safely on a trap is lost the moment its last adjacent friend steps
away or is removed. A push or pull always completes even when one of the
pieces involved is captured partway through, and the second movement of the
action still takes place.

## Turns and the null move

The side to move takes one to four steps as described above. The mover may
stop after any completed step or action; the two movements of a push or pull
count as two steps and cannot be split by stopping between them. A whole turn
whose resulting board is identical to the board at the start of the turn is
illegal.

## Standing positions and finished positions

A standing position is a board as it exists between turns. Because captures
are immediate, a standing position never contains a piece on a trap square
without an orthogonally adjacent friendly piece.

A standing position is finished, and no further turn is ever played from it,
when any of these holds: a Gold rabbit stands on rank 8, a Silver rabbit
stands on rank 1, Gold has no rabbits on the board, or Silver has no rabbits
on the board. Finished is judged only on standing positions: a board that
passes through such a state in the middle of a turn, for example a rabbit
pushed onto its goal rank and pulled back off before the turn ends, does not
end the game.

## Out of scope

The opening setup phase, move timing, and every history dependent rule,
including repetition restrictions, are outside this project. A query is a
bare position with no history, and turns are evaluated on positions alone.
