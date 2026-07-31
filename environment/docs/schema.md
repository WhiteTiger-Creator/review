# Graph schema

The fleet is stored as an embedded Kuzu database at `/app/graph/timesync.kuzu`.
It holds three node tables and two relationship tables.

## Node tables

### `Client`

A host whose clock is being audited.

| property | type | meaning |
|---|---|---|
| `id` | `INT64` | primary key |
| `name` | `STRING` | the client's name, unique across the fleet |

### `Server`

An upstream time source. One server may be used by several clients.

| property | type | meaning |
|---|---|---|
| `id` | `INT64` | primary key |
| `name` | `STRING` | the server's hostname, unique across the fleet |
| `stratum` | `INT64` | the server's own distance from a reference clock; `16` marks a server that is not synchronized |
| `root_dispersion` | `INT64` | the server's accumulated dispersion, in microseconds |
| `reachable` | `BOOLEAN` | whether the client's polls are currently reaching the server |

### `Candidate`

One measurement a client took against one server, expressed in microseconds as
offsets relative to the client's own clock. The correctness interval runs from
`lo` to `hi`, and `offset` is the single measured offset the interval was built
around. `lo` is never greater than `hi`, `offset` always lies within `[lo, hi]`,
and all three may be negative.

| property | type | meaning |
|---|---|---|
| `id` | `INT64` | primary key |
| `lo` | `INT64` | the low end of the correctness interval, inclusive |
| `hi` | `INT64` | the high end of the correctness interval, inclusive |
| `offset` | `INT64` | the measured clock offset, always within `[lo, hi]` |

## Relationship tables

| relationship | from | to | meaning |
|---|---|---|---|
| `OF` | `Candidate` | `Client` | the client that took this measurement |
| `FROM_SERVER` | `Candidate` | `Server` | the server this measurement was taken against |

Both relationships are directed and stored in the single direction shown, and
both are read only in that direction.

## Multiplicity

Every `Candidate` has exactly one `OF` relationship and exactly one
`FROM_SERVER` relationship. A `Client` has one or more candidates. Within a
single client the candidates come from distinct servers, so no client measures
the same server twice. Candidates belonging to one client never take part in
another client's certification. A `Server` may back candidates belonging to
several different clients.

The rules that decide the certification are stated in
`/app/docs/selection_rules.md`, and the required result shape is stated in
`/app/docs/output_contract.md`.
