# Tidefront simultaneous-turn adjudicator

This regular Project Terminus task exercises deterministic terminal game adjudication through `/app/bin/tidefront adjudicate`. The Go game engine uses a C lunisolar clock and interpolation library to determine navigable water depth before resolving simultaneous fleet movement, allied support, support cutting, territory control, and cumulative scoring.

## Difficulty explanation

Medium. The task requires coordinating strict validation, tide-dependent legality, simultaneous contests, support cutting, graph dependency chains and cycles, capture, scoring, canonical output, and digest generation. The measured worst-model pass rate is 60 percent, which places it at the upper boundary of the Medium tier.

## Solution explanation

The oracle completes the intentionally unfinished Go adjudicator while preserving the bundled C tide and astronomical-time engine. It validates the match, computes rounded turn depths, resolves moves and supports simultaneously, handles contests and occupancy dependencies, updates ownership and scores, then writes the canonical deterministic result and summary digest.

## Verification explanation

The 118-test verifier checks strict schemas and bounds, movement precedence, support activation and cutting, strength contests, chains, swaps, cycles, capture, cumulative scoring, winner tie breaks, tide and leap-second behavior, exact JSON shapes, digest records, stale-output cleanup, and determinism. Oracle passes 3 of 3 runs while the unchanged task fails, confirming the task is solvable without permitting a no-op solution.

## Environment note

The Dockerfile uses the exact digest-pinned canonical Go 1.24 Bookworm image from the current Terminal-Bench base-image list. The Go runtime and CGO-capable toolchain are required because both agents and the verifier rebuild the Go engine linked to the bundled C library.
