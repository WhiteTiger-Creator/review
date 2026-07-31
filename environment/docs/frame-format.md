# framekit frame format and dispatch contract

This document is the authoritative contract for auditing a framekit frame.
Where a shipped example appears to suggest something different from this text,
this text governs. Each case is a build configuration paired with one frame's
raw bytes, and the audit assigns each case exactly one verdict from the list
below. The disclosed source revisions under `reference/src` show the decode
paths this contract describes.

## Case inputs

A case supplies a build configuration text and a frame's raw bytes, `buf`.

The build configuration is a JSON object with two required fields:
`fast_path_compiled`, a boolean saying whether the `fast_path` feature is
compiled into that build, and `source_variant`, one of the strings `original`
or `guarded`, saying which decoder revision the build uses.

## Byte layout

`HEADER_SIZE = 13`. A frame's bytes, `buf`, are laid out:

- bytes 0..4: magic, must equal the ASCII bytes `FK01`.
- bytes 4..8: `outer_len`, an unsigned 32-bit little-endian integer.
- bytes 8..12: `sub_len`, an unsigned 32-bit little-endian integer.
- byte 12: a capability-flag byte; bit 0, the least significant bit, is the
  per-frame runtime request to use the fast decode path.
- bytes 13..: payload, whatever remains of `buf`.

`buf.len()`, the frame's actual physical length, is independent of what
`outer_len` claims. A frame whose declared lengths disagree with its actual
size is not malformed by that fact alone; the dispatch and arithmetic rules
below are exactly how that disagreement is supposed to be handled.

## The MALFORMED verdict

A case is `MALFORMED` when `buf.len() < HEADER_SIZE`, so the frame is
physically shorter than the fixed header and cannot be parsed at all, or when
the build configuration is not valid JSON, or when either required
build-configuration field is missing or of the wrong type. A malformed case
takes the `MALFORMED` verdict and no further rule applies to it.

## Evaluated verdicts

Once the frame is at least `HEADER_SIZE` bytes and the build configuration
parses, proceed in this exact order:

1. **Validator, magic.** If bytes 0..4 do not equal `FK01`, the verdict is
   `REJECT_MAGIC`.
2. **Validator, sanity ceiling.** Otherwise, if `outer_len`, read as a plain
   integer, exceeds `ABSOLUTE_MAX = 1_000_000_000`, the verdict is
   `REJECT_OUTER_LEN_BOUND`. The validator never compares `outer_len` against
   `sub_len`; no rule anywhere else does either.
3. **Dispatch.** The unsafe fast path is taken if and only if all three hold:
   `fast_path_compiled` is `true`, `source_variant` equals `original`, and
   bit 0 of the capability-flag byte, byte 12, is set. If any one of the three
   does not hold, the verdict is `SAFE_NO_UNSAFE_READ`. This covers the
   compiled-out case, the runtime-flag-unset case, and the guarded variant
   uniformly, regardless of what the arithmetic in step 4 would otherwise
   compute for the same bytes. The guarded variant's own arithmetic is fully
   checked and never reaches an unchecked read under any input.
4. **Arithmetic, fast path only.** All three quantities below are computed as
   64-bit unsigned integers with wrapping, modulo 2^64, semantics, matching
   Rust's `u64::wrapping_sub` and `wrapping_add` exactly:
   `payload_len = wrapping_sub(outer_len, HEADER_SIZE)`
   `body_len = wrapping_sub(payload_len, sub_len)`
   `end = wrapping_add(HEADER_SIZE, body_len)`
   The candidate read-range is `[HEADER_SIZE, end)`.
5. **Verdict.** If `end <= buf.len()`, the verdict is `REACHABLE_SAFE`: the
   fast path executed, but the range, after however much wrapping occurred,
   still fits inside the actual buffer. Otherwise the verdict is
   `REACHABLE_EXPLOITABLE:<HEADER_SIZE>-<end>`, naming the exact witness range
   that would be read out of bounds, with `HEADER_SIZE` and `end` written as
   plain decimal integers.

Carrying `end` through its own wraparound is not optional. An `outer_len` below
`HEADER_SIZE` alone already sends `payload_len` to a value near 2^64; adding
`HEADER_SIZE` back to a `body_len` that is itself near 2^64 can wrap `end` a
second time back below `buf.len()`. That case is `REACHABLE_SAFE`, even though
an intermediate subtraction underflowed. A rule that stops at whether a
subtraction underflowed, rather than computing `end` through both wraps,
decides this case wrong.

## What this contract does not cover

This contract does not evaluate payload contents in any way; payload bytes
beyond byte 13 never affect the verdict. Endianness of `outer_len` and
`sub_len` is always little-endian per this contract, exactly as the bytes are
laid out above; there is no alternate interpretation.

## Verdict summary

The six verdicts are `MALFORMED`, `REJECT_MAGIC`, `REJECT_OUTER_LEN_BOUND`,
`SAFE_NO_UNSAFE_READ`, `REACHABLE_SAFE`, and
`REACHABLE_EXPLOITABLE:<start>-<end>`.
