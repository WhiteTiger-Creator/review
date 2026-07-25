# Rounding-direction attributes

Every `scalbn` request names the rounding-direction attribute in force when its
exact product is mapped into the destination format. `logb` is exact and never
rounds. The five attributes are the ones defined by IEEE 754-2019 clause 4.3.

| Token | Attribute            | Rule                                              |
|-------|----------------------|---------------------------------------------------|
| `rne` | roundTiesToEven      | nearest; a tie goes to the even significand       |
| `rna` | roundTiesToAway      | nearest; a tie goes to the larger magnitude       |
| `rtp` | roundTowardPositive  | toward +infinity                                  |
| `rtn` | roundTowardNegative  | toward -infinity                                  |
| `rtz` | roundTowardZero      | toward zero (truncate the magnitude)              |

## Where the attribute changes the delivered datum

Whenever the destination cannot hold every bit of the exact product, the
attribute resolves the bits that are dropped. That happens wherever the product
carries more significant bits than the precision of the destination, and it
happens on the subnormal grid, where the significand is shortened further. A
non zero product that rounds to zero under one attribute may instead deliver
the least subnormal under another.

Where the magnitude exceeds the finite range of the destination the delivered
datum is the one IEEE 754-2019 clause 7.4 names for the attribute in force and
the sign of the result; the conditions raised are covered by
`exception-flags.md`.

Both edges are reached under default exception handling. Where the request
selects the exponent-adjusted delivery of `exception-handling.md`, the
attribute resolves the precision of the destination and nothing more.
