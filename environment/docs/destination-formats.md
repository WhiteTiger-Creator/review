# Destination formats

Every `scalbn` request names the interchange format its result is delivered
in. The token, the width of the encoding, and the widths of the three fields
are

| Token | Bits | Sign | Exponent field | Trailing significand | Hex digits |
|-------|------|------|----------------|----------------------|------------|
| `b16` | 16   | 1    | 5              | 10                   | 4          |
| `b32` | 32   | 1    | 8              | 23                   | 8          |
| `b64` | 64   | 1    | 11             | 52                   | 16         |

Each is a binary interchange format of IEEE 754-2019 clause 3.4, laid out as
`binary64-format.md` describes for the widest of the three: sign, then biased
exponent field, then trailing significand. The bias, the exponent range, and
the precision of each format are the ones the standard fixes for an exponent
field of that width, and the meaning of a reserved exponent field, of a
subnormal, and of a signed zero carries over unchanged.

`logb` names no destination. Its operand and its result are both binary64.

A `scalbn` operand is always a binary64 datum given in 16 hexadecimal
characters, whatever destination the request names; only the result changes
width. The exact product is mapped into the destination in a single step, so
no intermediate format takes part.
