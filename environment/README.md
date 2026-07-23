# Relaxation census toolkit

A small command line toolkit for relaxation bookkeeping of large thermal models. Given a
sparse conductance operator and a stream of census cases, it reports, per case, how many
modes of the patched model relax at a rate strictly below the case shift.

## Layout

- `include/` public types and the census entry point (`spectral.h`)
- `src/main.c` command line front end and per case orchestration
- `src/mtxread.c` reader for the Matrix Market symmetric coordinate operator
- `src/vecgen.c` deterministic shape vector generator used to expand a term seed
- `src/query.c` parser for the case file
- `src/counter.c` the census routine `count_modes_below`
- `scripts/fetch_operator.sh` retrieves the pinned conductance operator
- `docs/` operator, capacitance, patch, census and scale notes
- `data/examples/` sample case files

## Build and run

```
make
./scripts/fetch_operator.sh /app/operator.mtx
./mode_census /app/operator.mtx data/examples/slab_sweep.cse
```

Each case prints its census on its own line, in the order the cases appear in the file.

The front end, readers and generator are complete. The census routine
`count_modes_below` in `src/counter.c` is the single piece that decides each reported
number. It receives the conductance operator, the case shift and the two expanded patch
sets, and is responsible for everything else the census needs.
