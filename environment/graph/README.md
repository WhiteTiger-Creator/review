# Graph files

`cluster.nt` is the authoritative RDF dump of the cluster topology; the runner
in `bin/` loads it directly. It is N-Triples, so every line is a full subject,
predicate, object triple with absolute IRIs, and you can read it with ordinary
text tools as well as query it with SPARQL.

`seed.txt` records the seed the graph was generated from.
