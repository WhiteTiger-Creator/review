Audit the link aggregation state of a switch fabric.

The fabric is a Kuzu graph database at /app/graph/lacp_fabric.kuzu. It holds
switches, the ports they own, the physical cables between ports, and the per
switch aggregation configuration. Every port carries its own aggregation key
alongside the partner identity it advertises, and those advertised fields are
ordinary local configuration that nothing in the fabric checks. Operators have
made mistakes across this fabric, so the report has to reflect what the cabling
and the configuration actually imply rather than what any one port claims about
its neighbour.

The deliverable is a single Cypher query, written to /app/answer.cypher, that
reports the aggregation state of every port. It returns four columns named
switch, port, state and lag_id, emitting one row per port, each exactly once.
The state column carries one of four values, Detached, Individual, Bundled or
Down, and lag_id is either the port's group identifier or the literal NONE. Row
order is not significant.

The graph schema, with every property, every relationship and the fabric's
structural facts, is documented at /app/docs/schema.md. The complete set of
rules that decide a port's state is at /app/docs/aggregation_rules.md, and the
exact result contract is at /app/docs/output_contract.md. Those three documents
are the whole specification.

The image ships kuzu 0.6.1 and a runner at /app/bin/runquery.sh, which
evaluates a query file and prints the resulting rows, so a draft can be
executed while you work. Grading runs the query against other fabrics built to
this same schema.
