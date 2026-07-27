# Input format

The program takes two arguments: the directory holding the tables and the path
to a query file. Queries are handled in file order and each query's output is
written before the next one begins.

## Tables

Each table is a file named `<name>.csv` in the data directory. Its first line
is a header naming the feature columns and then the label column. Every later
line is one row: one integer per feature column followed by the integer class
label. Class labels start at zero. A feature entry of minus one means the
value was never recorded; every other feature entry is a non-negative integer.
Rows are indexed from zero in the order they appear after the header.

The same file layout serves both roles. A query names one table to train on
and one table to send down the fitted tree, and the two may be the same table.
Only the feature columns of the second table are used; its label column is
carried along but never consulted.

## Query lines

One query per line, blank lines ignored, exactly five whitespace separated
fields:

```
<qid> <train> <probe> <depth> <minimum>
```

- `qid` is an opaque identifier echoed at the start of every output line for
  that query.
- `train` names the table the tree is grown on, without its `.csv` suffix.
- `probe` names the table whose rows are sent down the fitted tree.
- `depth` is a decimal integer of at least one, the greatest depth an internal
  node may sit at.
- `minimum` is a decimal integer of at least two, the fewest rows a node may
  hold and still be split.

## Refused queries

A refused query emits `<qid> REJECT` as its only line. A query is refused when
the line does not have exactly five fields; either named table does not exist;
the depth or the minimum is not a non-negative decimal integer; the depth is
below one; the minimum is below two; either table is empty; or the two tables
do not carry the same number of feature columns.
