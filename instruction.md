Implement `/app/task_file/src/Program.cs` so `/app/task_file/Makefile` builds `/app/task_file/sphere-flux.exe`, a Mono-runnable C# spherical-harmonic quadrature tool. It integrates a real scalar field over an irregular polar mesh using the input, quadrature, and report contract in `/app/task_file/SPEC.md`; do not hard-code fixture outputs or delegate the math to external programs.

Treat the input as simple comma-split files, not quoted CSV. A double quote character in any field, including a token like `"bad"`, is malformed input and must trigger the same nonzero cleanup behavior as other malformed input.

With no arguments, read `/app/task_file/input` and write `/app/task_file/output` regardless of the current working directory. With two arguments, run as `mono /app/task_file/sphere-flux.exe <input_dir> <output_dir>`. Malformed input must exit nonzero and leave the requested output directory absent, deleting a stale directory at that path when present.

Successful runs write exactly `cell_flux.csv`, `ring_summary.csv`, `mode_coupling.csv`, `region_balance.json`, `gradient_audit.csv`, `latitude_frontier.csv`, `mode_spectrum.csv`, and `ring_mode_breakdown.csv`. Output must be deterministic: stable ordering from the spec, UTF-8 text, one final newline per file, six decimal digits for decimal fields, and rounded near-zero values emitted as `0.000000`.
