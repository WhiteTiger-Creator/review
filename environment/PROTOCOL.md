# Snapshot reclaim supervisor - operator manual

The reclaim supervisor decides which snapshots a storage pool keeps and which it
releases when the pool is short of free space. It is a fixed, fully
deterministic component: the same pool record always yields the same report.
This manual is the whole contract. Every rule the supervisor applies is written
below.

## Command

```
reclaim plan --pools <jsonl> --out <json>
```

`--pools` is a JSONL file holding one pool record per line. `--out` is the path
the report is written to. Both are required. A fatal input error exits nonzero
and writes no output file.

## Pool record

This is the record in `/app/samples/sample-01/pools.jsonl`, laid out for
reading:

```json
{
  "pool": "archive-a",
  "now": "2026-01-09T00:00:00Z",
  "keep": {"hourly": 1, "daily": 1, "weekly": 0, "monthly": 0},
  "target_blocks": 0,
  "snapshots": [
    {"id": "a-00", "taken": "2026-01-05T01:00:00Z"},
    {"id": "a-01", "taken": "2026-01-05T02:00:00Z"},
    {"id": "a-02", "taken": "2026-01-08T03:00:00Z"}
  ],
  "extents": [
    {"blocks": 100, "first": 0, "last": 1, "live": false},
    {"blocks": 40, "first": 0, "last": 0, "live": false},
    {"blocks": 7, "first": 1, "last": 2, "live": false},
    {"blocks": 500, "first": 2, "last": 2, "live": true}
  ]
}
```

A snapshot may also carry the two optional fields, as in
`{"id": "d-01", "taken": "...", "hold_until": "2026-05-01T00:00:00Z", "clone": true}`.

- Every timestamp is UTC in exactly the form `YYYY-MM-DDTHH:MM:SSZ`.
- `snapshots` is in taken order, oldest first, strictly increasing. Its position
  in this list is a snapshot's **index**, counted from 0.
- `hold_until` is optional. `clone` is optional and defaults to false.
- `keep` carries one non-negative count for each of the four tiers `hourly`,
  `daily`, `weekly`, `monthly`.
- `target_blocks` is the number of blocks the pool needs to release.

### Extents

An extent is a run of blocks that the pool's snapshots share. It records the
snapshot indices that reference it:

- `first` and `last` are indices, `0 <= first <= last < len(snapshots)`. The
  extent is referenced by **every** snapshot with an index in `first..last`
  inclusive.
- `live` is true when the pool's current filesystem also references the extent.

A pool may list several extents with the same span, and an index may appear in
any number of extents.

### Fatal input

Exit nonzero and write nothing when: a pool name repeats within the file, a
snapshot id repeats within a pool, `snapshots` is empty or not strictly
increasing in `taken`, a timestamp is not in the exact form above, a `keep`
count or `target_blocks` is negative or missing, `blocks` is not a positive
integer, an extent index is out of range, or `first` is greater than `last`.

## Retention

### Anchors

A snapshot is an **anchor** when its `hold_until` is strictly later than the
pool's `now`, or when `clone` is true. A `hold_until` at or before `now` has
expired and does nothing. Anchors are always kept and are never released, at any
point in the run.

### Periods and representatives

Each tier sorts the snapshots into periods by a key taken from the snapshot's
`taken` timestamp:

| tier | period key |
|---|---|
| `hourly` | the first 13 characters, `YYYY-MM-DDTHH` |
| `daily` | the first 10 characters, `YYYY-MM-DD` |
| `weekly` | the date of the Monday of that UTC week, `YYYY-MM-DD` |
| `monthly` | the first 7 characters, `YYYY-MM` |

Within a period the **representative** is the snapshot with the lowest index,
that is the first one taken in that period. Only a representative is ever kept
on account of a tier.

### Spending the keep counts

Take the tiers in the order `hourly`, `daily`, `weekly`, `monthly`. For a tier
whose count is `k`, walk that tier's period keys from the newest key downwards
and stop once `k` slots have been spent or the keys run out:

- If the period's representative is an anchor, **skip the period without
  spending a slot**. An anchor is already kept, so it does not cost the tier
  anything and the tier reaches one period further back.
- Otherwise keep that representative and spend one slot. A representative that
  an earlier tier already kept still spends a slot in this tier.

Tiers never look at what another tier kept when deciding whether a slot is
spent. Only anchors are free.

A snapshot that no anchor and no tier kept is **released**.

### Retention class

Report the first class that applies, in this order: `hold`, `clone`, `hourly`,
`daily`, `weekly`, `monthly`.

## Released blocks

Releasing a set of snapshots frees an extent only when nothing is left holding
it. An extent is freed when `live` is false **and** every index in
`first..last` was released. If even one snapshot in that span survives, the
whole extent stays, and its blocks do not count.

`freed_blocks` is the sum of `blocks` over the freed extents, computed once
against the snapshots that survive at the end of the run.

## The reclaim ladder

The supervisor begins with the pool's own `keep` counts, works out what
survives, and adds up the blocks that would be released.

If that total is greater than or equal to `target_blocks`, the run is over.
Otherwise the supervisor takes one relaxation step and works the whole thing out
again from the start with the reduced counts:

> A relaxation step subtracts 1 from the first tier whose count is still above
> zero, taking the tiers in the order `hourly`, `daily`, `weekly`, `monthly`.

The supervisor keeps stepping until the released total reaches the target or
every one of the four counts is zero, whichever comes first. `passes` is the
number of relaxation steps taken, so it is 0 when the pool's own counts were
already enough. Anchors survive every step.

`freed_blocks` in the report describes the surviving set the run ended on. It is
not a running total, and the totals reached at earlier steps are discarded.

`shortfall` is `target_blocks - freed_blocks` when the run ended short, and 0
otherwise.

## Report

```json
{
  "pools": [
    {
      "pool": "archive-a",
      "passes": 0,
      "keep_final": {"hourly": 1, "daily": 1, "weekly": 0, "monthly": 0},
      "retained": [{"id": "a-02", "class": "hourly"}],
      "pruned": ["a-00", "a-01"],
      "freed_blocks": 140,
      "shortfall": 0,
      "digest": "66855125ef92a95bca4aa0bc687eb19685cf316ea1d947c3012ff15ec6273890"
    }
  ],
  "digest": "ccf3a2f4c2b5fe02d477f82d4a6db07a24c5c3162d4c4b09a60e1b007a96afcd"
}
```

- `pools` is sorted by `pool` name, ascending.
- `keep_final` is the counts the run ended on.
- `retained` and `pruned` list snapshots in **taken order**, that is by
  ascending index, not by id.
- Every field is required on every pool row.

### Digests

A pool's `digest` is the lowercase hex SHA-256 of a UTF-8 text built from seven
lines, each one closed by a single newline, including the last:

1. the pool name
2. `passes`
3. `keep_final` as `<hourly>,<daily>,<weekly>,<monthly>`
4. the `retained` rows, each written as the id, a colon and the class, joined
   with `;`
5. the `pruned` ids joined with `;`
6. `freed_blocks`
7. `shortfall`

An empty list writes an empty line. Integers are written in decimal with no
padding and no sign. For the sample above the text is
`archive-a\n0\n1,1,0,0\na-02:hourly\na-00;a-01\n140\n0\n`.

The report `digest` is the lowercase hex SHA-256 of the UTF-8 text formed by
writing, for each pool row in report order, the pool name, one space, that
row's digest, and a newline.

## Worked examples

`/app/samples/` holds six pool records with the report the supervisor produced
for each one. Between them they exercise every rule above: shared extents that
only a run of releases can free, anchors that do not spend a slot, the earliest
snapshot in a period as its representative, a ladder that runs several steps, an
expired hold, a target that cannot be met, and all four retention classes.
