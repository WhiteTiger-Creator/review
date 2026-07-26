# scalbn

`scalbn(x, n)` returns `x` multiplied by two raised to the integer power `n`,
with the exact product mapped into the destination format of
`destination-formats.md` under the three attributes named on the request line:
the rounding-direction attribute of `rounding-modes.md`, and the
exception-handling and tininess-detection attributes of
`exception-handling.md`.

A zero or infinite operand is returned with its sign in the destination
format, and a Not a Number operand is carried through with its payload taken
from the leading bits of the operand's trailing significand and delivered
quiet; a signalling operand is handled as the standard requires for signalling
inputs. None of these cases consults an attribute.

For a finite non zero operand the exact product may land anywhere on the real
line, and may carry more significant bits than the destination holds. When it
falls into the region below the smallest normal magnitude of the destination
the result is formed under gradual underflow: the surviving significand bits
are rounded per the mode, so a product that rounds to zero under one attribute
may round up to the least subnormal under another, and the conditions raised
depend on whether that mapping is exact.

When the magnitude exceeds the finite range of the destination the operation
overflows and the delivered datum follows `rounding-modes.md`. A scale `n` of
very large magnitude in either direction is accepted and handled at the range
limits.

Both range regions are reached through the exception-handling attribute of the
request. Where that attribute selects the exponent-adjusted delivery of
`exception-handling.md`, the product is instead rescaled by the standard's
fixed adjustment, which changes both the delivered datum and the conditions
raised.
