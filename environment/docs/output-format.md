# Output contract

Write the SPARQL query as plain text to the absolute path `/app/answer.sparql`.

The query must be a `SELECT` projecting exactly three variables, named and
ordered as `?pod`, `?schedulable`, `?feasible_node_count`.

- `?pod` is the IRI of a pending pod.
- `?schedulable` must render as `true` or `false`.
- `?feasible_node_count` must be an exact integer. It is a count of worker
  nodes, so no arithmetic tolerance applies anywhere in this task and no
  rounding is involved.

Every pending pod must appear exactly once, including a pod whose feasible node
count is zero, which is reported as a row with the count `0` and never as an
absent row. No cell may be left unbound. No pod that is not pending may appear.
Extra or differently named columns are a contract violation. Row order does not
matter; the set of rows is what gets checked.

You can run a query against the committed graph at any time with:

    /app/bin/runquery.sh /app/answer.sparql

It prints the rows it produces so you can inspect them. The runner is read-only
and loads the graph from `/app/graph/cluster.nt`.
