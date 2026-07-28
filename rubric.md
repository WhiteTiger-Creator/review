# Rubric 1
Agent implements `/app/bin/tidefront adjudicate` as the documented fail-closed interface, requiring absolute input and output paths, a positive thread count, strict JSON parsing, complete reference validation, and stale-output removal on every failure, +3
Agent computes each turn on the TAI timeline, preserves declared leap seconds, evaluates the bundled harmonic tide model, applies ties-to-even six-decimal rounding with negative-zero normalization, and uses rounded effective depth for legality, +3
Agent resolves hold and move orders from each turn's current positions, rejects same-node and non-edge moves with the documented precedence, and excludes edge- or depth-blocked fleets from contests and support cutting, +3
Agent validates and activates only legal allied support for the supported fleet's exact move, cuts support only for qualifying enemy candidate attacks, and aggregates active support into contest strength before deterministic tie breaks, +5
Agent resolves same-target contests by supported strength then initiative, player ID, and fleet ID while ensuring contest losers remain occupants that can block dependent movement, +5
Agent resolves occupancy dependencies simultaneously across chains into empty nodes, chains ending at stationary fleets, swaps, closed cycles, broken cycles, disjoint components, and supported winners without sequential artifacts or duplicate occupancy, +5
Agent applies post-movement capture and retained ownership, awards node values every turn, accumulates scores, and selects the winner by score then initiative then player ID, +5
Agent emits the exact documented compact JSON field order and fleet-row shapes, canonical sorted arrays, one trailing newline, the canonical SHA-256 summary digest, and byte-identical results across input order, thread counts, working directories, and repeated runs, +5
Agent replaces the adjudicator with a tide-only forecast command, bypasses the required Go and C application path, or hardcodes the bundled match instead of implementing general rules, -5
Agent treats support as unconditional, permits invalid or same-player attacks to cut support, ignores supported strength, or lets support bypass contest and occupancy dependency rules, -5
Agent resolves fleets sequentially, makes outcomes depend on input order, mishandles contest losers, chains, swaps, or cycles, or produces duplicate final occupancy, -5
Agent accepts malformed match data, emits missing or extra result fields, computes a noncanonical digest, publishes partial output, or leaves stale output after failure, -5
