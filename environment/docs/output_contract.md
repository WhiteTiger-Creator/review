# Output contract

Write the finished Cypher query, and nothing else, to `/app/answer.cypher`.
The file must hold one single Cypher statement.

## Result columns

The query returns exactly four columns, named and ordered as follows.

| column | type | value |
|---|---|---|
| `switch` | `STRING` | `Switch.name` of the switch owning the port |
| `port` | `STRING` | `Port.name` |
| `state` | `STRING` | one of `Detached`, `Individual`, `Bundled`, `Down` |
| `lag_id` | `STRING` | the group identifier, or the literal `NONE` |

## Cardinality and comparison

Every port in the graph appears exactly once. A port must never be dropped and
never duplicated, whatever its state.

Row order does not matter; the result is compared as a set of rows. Every value
is a string or an integer, so no numeric tolerance applies. `lag_id` is always
a non-empty string: for ports with no group it is the four-character literal
`NONE`, never an empty string, never null, and never unbound.

## Running it

Run a query against the visible graph with the runner:

```bash
bash /app/bin/runquery.sh /app/answer.cypher
```

The runner also accepts a query as a literal argument instead of a path, and
prints a header row of column names followed by one tab-separated row per
result. `bash /app/bin/list_schema.sh` prints the graph's tables.

The query is evaluated against other fabrics built to the same schema, not only
the one shipped at `/app/graph/lacp_fabric.kuzu`.
