# Tidefront simultaneous-turn adjudicator

This regular Project Terminus task exercises deterministic terminal game adjudication through `/app/bin/tidefront adjudicate`. The Go game engine uses a C lunisolar clock and interpolation library to determine navigable water depth before resolving simultaneous fleet orders, board capture, and cumulative scoring.

## Difficulty explanation

Medium. The task combines strict JSON validation, CGO tide evaluation, simultaneous graph resolution, and deterministic serialization. The measured worst-model pass rate is 40 percent, which falls in the Project Terminus Medium band.

## Solution explanation

The oracle completes the three intentionally incomplete Go files used by `/app/bin/tidefront adjudicate`. It implements strict match validation, fleet-order legality and simultaneous dependency resolution, territory capture and scoring, winner selection, and canonical digest generation while preserving the bundled C tide and time engine.

## Verification explanation

The oracle passes all 88 verifier cases and NOP passes none. The suite covers strict input handling, TAI and tide calculations, rounded-depth movement legality, contests, chains, cycles, swaps, capture, retained ownership, cumulative scoring, winner tie-breaks, canonical JSON, SHA-256 records, determinism, and fail-closed output cleanup.

## Environment note

The Dockerfile uses the exact digest-pinned canonical Go 1.24 Bookworm image from the current Terminal-Bench base-image list. The Go runtime and CGO-capable toolchain are required because both agents and the verifier rebuild the Go engine linked to the bundled C library.
