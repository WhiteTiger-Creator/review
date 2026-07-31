# Namespaces

All application terms use a single namespace, abbreviated `:` in the schema
notes:

    http://ex.org/k8s#

Node identifiers and predicates are IRIs under that namespace, for example
`http://ex.org/k8s#hasTaint`. Type triples use the standard RDF type predicate:

    http://www.w3.org/1999/02/22-rdf-syntax-ns#type

The `:pending` object is a typed `xsd:boolean` literal. Every other literal in
the graph is a plain string with no language tag and no datatype, including the
key, value, effect, operator and topology key fields.

The data is serialized as N-Triples in `/app/graph/cluster.nt`, so every line is
a fully written out subject, predicate, object triple with absolute IRIs. When
you write SPARQL you can declare `PREFIX : <http://ex.org/k8s#>` and use the
short `:name` form.
