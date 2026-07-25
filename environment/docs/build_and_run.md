# Build and run

Run `make` in the project root. It compiles every `.cpp` file under `src/`
with the system C++ compiler into a binary called `retro`.

Run the binary by piping query lines into it:

```
printf '7r/8/8/3R4/8/8/8/8 g\n' | ./retro
```

The scaffold already parses queries and prints one integer per line; the
counting function stubbed in `/app/src/retro.cpp` is the missing engine.

The forward rules are provided so you do not have to reimplement them.
`/app/src/rules.hpp` is a header-only module in namespace `arimaa` that
applies one legal action to a board under the full rules in
`/app/docs/rules.md`: `apply_step`, `apply_push`, and `apply_pull` each take a
board, the mover color (0 for Gold, 1 for Silver), and the squares involved,
and return whether the action is legal, writing the resulting board with trap
captures already resolved. It also exposes `is_frozen`, `resolve_traps`,
`adjacent`, `neighbors`, `strength_of`, `color_of`, and the trap squares.
Boards are `std::array<char, 64>` indexed `rank * 8 + file`, matching the
`sq` field of the parsed position; using this module or not is your choice,
and it never counts predecessors for you.

`/app/data/sample_positions.txt` holds sample queries, one per line, with the
expected count as the trailing field. They run cheapest first; the last five
are dense or busy positions of the same character as the graded batch.
`/app/run_samples.sh` rebuilds the binary, replays all of them, and prints the
per-query and total wall time, so the speed of an engine on batch-like
input is measurable from the first minute.

That script caps each query at 45 seconds and stops after two capped
queries, reporting `SLOW` instead of an answer. A cap means the engine is far
over budget, not that the query is unanswerable. Nothing in this project
should ever be left running without a bound: when timing a single query by
hand, wrap it, for example `printf '<query>\n' | timeout 60 ./retro`.

The grader rebuilds the same sources the same way, feeds the program one
batch of about a hundred queries on standard input, and requires the whole
batch to finish within 1200 seconds on comparable hardware, comparing every
printed integer exactly. That is an average of roughly thirteen seconds per
query, and the batch is dominated by dense and busy positions like the last
samples, so the budget is set by how fast the engine handles exactly those
shapes; a correct engine that is too slow on them scores nothing. A reference
engine answers the heaviest of these positions in a few seconds.

The graded queries are not limited to the shapes shown in the samples. They
exercise every rule in `/app/docs/rules.md` and every way a piece can leave
the board during a turn, including positions built specifically to separate
engines that handle captures, freezing, mid-turn trap timing, or the full
four-step reversal only partially. The grader compiles whatever `/app/src`
contains when the session ends. Only the C++ standard library is available.
