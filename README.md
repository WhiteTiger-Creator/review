# Tidefront simultaneous-turn adjudicator

This regular Project Terminus task exercises deterministic terminal game adjudication through `/app/bin/tidefront adjudicate`. The Go game engine uses a C lunisolar clock and interpolation library to determine navigable water depth before resolving simultaneous fleet orders, board capture, and cumulative scoring.

## Difficulty explanation

Medium. Claude Opus 4.8 and GPT-5.5 each passed 3 of 5 measured runs, giving a 60 percent worst-model rate at the upper boundary of the Medium band. The difficulty comes from integrating strict validation and tide-derived rounded movement legality with simultaneous contests, occupancy dependency chains and cycles, capture, cumulative scoring, winner tie-breaks, and canonical deterministic output.

## Solution explanation

The oracle completes the three intentionally incomplete Go files behind the actual `/app/bin/tidefront adjudicate` command while preserving the bundled C tide and time engine. It implements strict input validation, movement and rounded-depth precedence, contest priority, simultaneous chain and cycle resolution, territory capture, retained ownership, scoring, winner selection, canonical serialization, and digest generation.

## Verification explanation

The oracle passes all 88 verifier cases in each reference run and NOP passes none. The suite checks the real adjudication interface, malformed-input rejection, TAI and tide calculations, movement legality, contests, chains, cycles, swaps, capture, retained territory, cumulative scoring, winner tie-breaks, canonical JSON and SHA-256 records, determinism, and fail-closed stale-output cleanup.

## Environment note

The Dockerfile uses the exact digest-pinned canonical Go 1.24 Bookworm image from the current Terminal-Bench base-image list. The Go runtime and CGO-capable toolchain are required because both agents and the verifier rebuild the Go engine linked to the bundled C library.
