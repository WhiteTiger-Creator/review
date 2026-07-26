# Arimaa turn undo counter

A small C++ project that counts, for a given Arimaa position and the color
that just moved, the exact number of distinct boards from which one complete
legal turn produces that position.

- `docs/rules.md` is the complete rule set in scope.
- `docs/io_contract.md` defines the query format and the exact meaning of
  the printed integer.
- `docs/build_and_run.md` covers building, running, and the batch time
  budget.
- `data/sample_positions.txt` holds sample queries with expected answers.

The engine lives in `src/retro.cpp`; the rest of `src/` is a working
scaffold.
