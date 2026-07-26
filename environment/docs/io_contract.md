# Input and output contract

The program reads queries from standard input until end of file. Each query
is one line with two whitespace separated fields:

```
<placement> <mover>
```

- `placement` is eight ranks from rank 8 down to rank 1, separated by `/`.
  Within a rank the squares run from file `a` to file `h`. A digit `1` to `8`
  is that many consecutive empty squares. A letter is a piece: `E` elephant,
  `M` camel, `H` horse, `D` dog, `C` cat, `R` rabbit, uppercase for Gold and
  lowercase for Silver. The placement describes a standing position as
  defined in /app/docs/rules.md, reached at the end of a turn.
- `mover` is `g` when Gold made that last turn and `s` when Silver made it.

For each query the program prints one line to standard output: a single
integer, and nothing else.

## What the integer counts

The integer is the exact number of distinct boards Q satisfying all of the
following, for the queried board P and mover color:

1. Q is a standing position as defined in /app/docs/rules.md: no piece stands on
   a trap square without an orthogonally adjacent friendly piece, and Q is
   not finished.
2. One complete legal turn by the mover color, played from Q under the full
   rules in /app/docs/rules.md, can leave exactly the board P.
3. Q contains at most one piece more than P. Boards from which the turn
   captured two or more pieces are excluded from the count by this piece
   budget, and boards with a lower piece count than P can never reach it.

Two different turns from the same Q count once; the count is over boards Q,
not over turns. The count may legitimately be zero: some boards cannot be
the result of any legal turn under the piece budget. Piece inventories are
respected throughout: no color ever exceeds one elephant, one camel, two
horses, two dogs, two cats, and eight rabbits.

## Worked examples

The sample file /app/data/sample_positions.txt holds queries with their expected
counts, including small positions whose count can be reasoned through by
hand and full board positions where captures are impossible because both
inventories are complete.

## Performance

The grader runs the compiled program once on a batch of about a hundred queries,
dominated by dense and busy positions, and enforces a total time budget for
the whole batch, stated in
/app/docs/build_and_run.md. Correct but slow counting strategies exist that do
not fit this budget; the program must be efficient as well as exact.
