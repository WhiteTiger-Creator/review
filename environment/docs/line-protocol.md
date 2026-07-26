# Input and output format

Each request is expressed as one line, in one of two forms.

```
logb <x>
scalbn <x> <n> <dest> <mode> <handling> <tininess>
```

`<x>` is exactly 16 hexadecimal characters (upper or lower case) encoding the
64 bits of a binary64 datum, most significant bit first. `<n>` is a signed
decimal integer scale for `scalbn`. `<dest>` is the destination format of the
result, one of `b16`, `b32`, or `b64`, defined in `destination-formats.md`.
`<mode>` is the rounding-direction attribute in force for that `scalbn`, one of
`rne`, `rna`, `rtp`, `rtn`, or `rtz`; the modes are defined in
`rounding-modes.md`. `<handling>` is the exception-handling attribute, `def` or
`wrap`, and `<tininess>` is the tininess-detection attribute, `tb` or `ta`;
both are defined in `exception-handling.md`. `logb` answers in binary64 and
carries no destination or attribute.

Fields are separated by single spaces. Leading and trailing whitespace is
ignored. A blank line, or a line whose first non whitespace character is `#`,
produces no output. A line that does not match either form exactly, including
lines with an unparseable operand, an unrecognised destination or attribute
token, or the wrong field count, produces no output.

Every accepted request produces exactly one output line, in input order.
