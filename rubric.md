Agent uses the real `/app/bin/tidefront adjudicate` interface, preserves the Go and C build path, supplies the documented absolute-path flags, and rejects non-positive `--threads`, +3
Agent validates the complete strict match contract including numeric bounds, uniqueness, references, order shapes, duplicate keys, unknown fields, and trailing JSON before publishing output, +5
Agent computes TAI turn timestamps and harmonic tide samples, rounds tide and effective depth to six decimals with ties to even, normalizes negative zero, and applies edge-before-depth movement legality from each turn's current positions, +5
Agent resolves same-target contests only among legal candidate moves using initiative, player ID, and fleet ID priority without allowing blocked moves to influence the winner, +3
Agent resolves fleet occupancy simultaneously across chains, swaps, closed cycles, contest winners and losers, and stationary blockers without sequential artifacts or duplicate final occupancy, +5
Agent applies post-movement territory capture, retained ownership, per-turn ownership score deltas, cumulative scores, and final winner tie-breaks by score, initiative, and player ID, +5
Agent emits the documented chronologically ordered compact result, sorted node, fleet, and score arrays, one trailing newline, and the correct SHA-256 summary records, +5
Agent checks fail-closed stale-output removal and byte-identical behavior across repeated runs, worker counts, input orderings, and working directories, +3
Agent replaces or bypasses `/app/bin/tidefront adjudicate` with a nonexistent `tidecast forecast` or other tide-only command path, -5
Agent resolves fleet orders sequentially, allows multiple fleets to finish on one node, or mishandles dependency chains and cycles, -5
Agent accepts malformed input, publishes partial output, or leaves a stale output file after failed adjudication, -5
Agent hardcodes the bundled match or produces results that vary with worker count, input ordering, repeated execution, or working directory, -5
