# SPARQL quickstart (Oxigraph)

The graph runs on Oxigraph, an embedded RDF store queried with standard
SPARQL 1.1. A few constructs that come up in everyday SPARQL 1.1 queries:

- A triple pattern with a fixed subject or object, for example
  `:some_iri :pred ?x`, anchors the match to that specific node.
- The semicolon separator lets one subject carry several predicates in a row,
  as in `?t :key ?k ; :value ?v`.
- `FILTER` restricts matched bindings by an arbitrary boolean expression;
  `OPTIONAL` includes a pattern's bindings when present without dropping rows
  where it does not match.
- `UNION` combines the results of two alternative graph patterns.
- `EXISTS` and `NOT EXISTS` test whether a pattern has any match under the
  current bindings, and they may be nested inside one another.
- `COUNT` with `GROUP BY` summarizes the matches for each group into a single
  value, and `SELECT DISTINCT` keeps only the distinct bindings a pattern
  produces.
- A `SELECT` may project a computed expression under a new name with the
  `(expr AS ?name)` form, and that expression may be an aggregate.

This file is a syntax reference only; it does not describe this task's graph
or question.
