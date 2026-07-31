# Cluster placement query

This environment holds a Kubernetes-style cluster topology as RDF and asks for a
single SPARQL query. Start with `docs/schema.md` for the vocabulary and the
shape of the data, `docs/placement_rules.md` for the exact rules the audit
applies, and `docs/output-format.md` for where to write the answer and how to
test it. `docs/graph-overview.md` describes the contents of the graph and
`docs/namespaces.md` the IRI and literal conventions. `docs/query-quickstart.md`
is a generic SPARQL syntax reference if you need it.

The graph lives at `graph/cluster.nt` (see `graph/README.md` for what that
directory holds). Use `bin/runquery.sh` to execute a query file against the
graph.
