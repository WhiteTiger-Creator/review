# IEEE 754 logb and scalbn exception semantics

An IEEE 754-2019 conformance exercise: compute the `logb` and `scalbn`
operations, reading one request per line and evaluating one result line each.

## Input and output format

Each input line is either `logb <x>` or
`scalbn <x> <n> <dest> <mode> <handling> <tininess>`. The operand `x` is a 16
character lower or upper case hexadecimal string giving the 64 bit encoding of
a binary64 datum. The scale `n` is a signed decimal integer, `dest` is the
destination format the result is delivered in, one of `b16`, `b32`, or `b64`
(see `docs/destination-formats.md`), `mode` is the rounding-direction
attribute for that `scalbn`, one of `rne`, `rna`, `rtp`, `rtn`, or `rtz` (see
`docs/rounding-modes.md`), `handling` is the exception-handling attribute
`def` or `wrap`, and `tininess` is the tininess-detection attribute `tb` or
`ta`; the last two are defined in `docs/exception-handling.md`. Blank lines
and lines whose first non space character is `#` are ignored, as are lines
that do not parse as one of the two forms.

## Output

For every accepted request the evaluator reports the hexadecimal encoding of
the result in the format it was delivered in, a single space, and a five
character flag mask in the fixed order Invalid, DivByZero, Overflow,
Underflow, ineXact, where each character is `1` when the corresponding
exception is signalled and `0` otherwise.

## Build and run

```
cargo build --release --offline
./target/release/fpexp < data/sample-logb.in
```

The `docs` directory states the operation semantics and the encoding
layouts. The `data` directory holds sample inputs with their expected
outputs.
