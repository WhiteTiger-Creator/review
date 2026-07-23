# Operator source

The conductance operator is a large sparse symmetric positive definite matrix drawn from
a steady state thermal finite element model, distributed through the SuiteSparse matrix
collection. It has on the order of 1.2 million degrees of freedom and a few million
stored nonzeros in its lower triangle.

`scripts/fetch_operator.sh` retrieves the operator over the network and verifies it
against a fixed content hash, then writes it to the path given as its first argument
(by convention `/app/operator.mtx`). The operator is not part of the image and must be
fetched before the toolkit can run.

The file is in Matrix Market symmetric coordinate real format: a header line with the
row count, column count and stored nonzero count, followed by one line per stored entry
holding a one based row index, a one based column index and a value. Only the lower
triangle including the diagonal is stored; the operator is symmetric.
