# Emit contract orientation

Operators treat the emitted JSON as the authoritative audit for one manifest run. Row digests cover per-unit pipe serializations; the top digest covers the header line plus each row serialization in manifest unit order.

The instruction at `/app/instruction.md` states the tested field formulas and digest packing rules used by verifiers.

Verifier logs are collected through pytest's `--ctrf` report flag; it is not an application argument.
