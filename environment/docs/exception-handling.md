# Exception-handling and tininess-detection attributes

After its destination format and its rounding-direction attribute every
`scalbn` request names an exception-handling attribute and a
tininess-detection attribute. `logb` consults neither.

## Exception handling

| Token  | Attribute                                                        |
|--------|------------------------------------------------------------------|
| `def`  | default handling of the overflow and underflow conditions        |
| `wrap` | exponent-adjusted alternate handling of those two conditions     |

Under `def` the conditions are delivered as `exception-flags.md` and
`rounding-modes.md` describe: an overflowing magnitude saturates to an
infinity or to the largest finite value of the destination, and a tiny
magnitude is mapped onto the subnormal grid of the destination or to zero.

Under `wrap` the alternate handling of IEEE 754-2019 clause 8.2 applies. The
result is computed as if the exponent range were unbounded, rounded to the
precision of the destination under the rounding-direction attribute, and its
exponent then adjusted by the amount that clause fixes for a format with that
exponent field width. The adjustment is subtracted from the exponent of an
overflowing result and added to the exponent of a tiny one; the condition
itself is still signalled. Under this attribute the two conditions rest on the
range of that rounded result alone.

The exponent adjustment is not itself a loss of accuracy: ineXact reports
only what the rounding to the precision of the destination lost.

The adjustment is applied at most once. If the adjusted exponent still falls
outside the range of the normal numbers of the destination, the request is
delivered exactly as default handling would deliver it, and raises exactly the
conditions default handling would raise.

## Tininess detection

| Token | Attribute                                                |
|-------|----------------------------------------------------------|
| `tb`  | tininess judged on the exact result, before rounding     |
| `ta`  | tininess judged on the delivered result, after rounding  |

Underflow under default handling requires tininess together with a loss of
accuracy. IEEE 754-2019 clause 7.5 permits either detection and an
implementation must state which it uses; here the request states it, so both
are exercised. In no case does the attribute change the delivered bits.
