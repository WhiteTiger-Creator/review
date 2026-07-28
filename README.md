# Tidefront simultaneous-turn adjudicator

This regular Project Terminus task exercises deterministic terminal game adjudication through `/app/bin/tidefront adjudicate`. The Go game engine uses a C lunisolar clock and interpolation library to determine navigable water depth before resolving simultaneous fleet movement, allied support, support cutting, territory control, and cumulative scoring.

## Difficulty explanation

Hard. The revision adds 30 documented behavioral tests around strict support-order validation, rounded support reachability, support cutting before contests, strength aggregation, exact output rows, and interactions with occupancy chains, capture, scoring, digests, and determinism. These rules require a multi-phase start-of-turn algorithm rather than a local extension to the previous move resolver.

## Solution explanation

The oracle completes the intentionally incomplete Go adjudicator while preserving the bundled C tide and astronomical-time engine. It implements strict input validation, current-position and rounded-depth legality, allied support activation and cutting, strength-based contests, simultaneous chain and cycle resolution, territory ownership, scoring, canonical serialization, and digest generation.

## Verification explanation

The verifier retains the prior movement, validation, tide, scoring, schema, digest, and determinism coverage and adds 30 focused support cases, including six combined scenarios spanning three or more rules. Expected outcomes are asserted from the public contract and direct analytical calculations. The oracle passes the full suite and the unchanged starter implementation fails.

## Environment note

The Dockerfile uses the exact digest-pinned canonical Go 1.24 Bookworm image from the current Terminal-Bench base-image list. The Go runtime and CGO-capable toolchain are required because both agents and the verifier rebuild the Go engine linked to the bundled C library.
