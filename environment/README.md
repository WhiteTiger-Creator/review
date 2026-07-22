# Modal count toolkit

A small command line toolkit for spectral bookkeeping of large symmetric operators.
Given a symmetric operator and a stream of query cases, it reports, per case, how many
eigenvalues of a modified version of the operator fall strictly below a query shift.

## Layout

- `include/` public types and the counting entry point (`spectral.h`)
- `src/main.c` command line front end and per case orchestration
- `src/mtxread.c` reader for the Matrix Market symmetric coordinate operator
- `src/vecgen.c` deterministic mode vector generator used to expand a term seed
- `src/query.c` parser for the query file
- `src/counter.c` the counting routine `count_eig_below`
- `scripts/fetch_operator.sh` retrieves the pinned operator
- `docs/` operator, query, modification and scale notes
- `data/examples/` sample query files

## Build and run

```
make
./scripts/fetch_operator.sh /app/operator.mtx
./spectral_count /app/operator.mtx data/examples/case_a.qry
```

The front end, readers and generator are complete. The counting routine
`count_eig_below` in `src/counter.c` is the single piece that decides each reported
count.
