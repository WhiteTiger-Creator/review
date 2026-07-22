# Query records

A query file begins with a single integer giving the number of cases. Each case then
consists of a header line with two fields, the query shift and the number of
modification terms, followed by one line per modification term.

Each modification term line has two fields: a real weight and an unsigned 64 bit seed.
The seed expands into a dense unit length mode vector through the generator in
`src/vecgen.c`; the same seed always yields the same vector for a given operator size.
A case with zero terms leaves the operator unmodified.

Shifts are given as real numbers. Weights may be positive or negative. The reader in
`src/query.c` returns the parsed cases; the front end expands each term seed into its
vector before handing the case to the counting routine.
