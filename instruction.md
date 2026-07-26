IEEE 754-2019 pins down what logb and scalbn deliver and which exceptions they
raise. Reproduce both exactly.

logb answers the radix two exponent of a binary64 operand, itself in binary64.
scalbn multiplies its binary64 operand by two raised to a signed integer power,
mapping that exact product in a single rounding into the interchange format the
request names: binary16, binary32, or binary64. Three attributes ride with every
scalbn and move the answer: one of five rounding directions, an exception
handling that is either the default or the exponent adjusted alternate of
clause 8.2, and tininess detected before or after rounding.

Operands are sixteen hexadecimal characters spelling all 64 bits, so signed
zeros, infinities, quiet and signalling Not a Number operands, and every
destination's subnormal boundary and exponent extremes are in range. Those
corners separate a conforming result from a plausible one: there the attributes
decide what an overflow delivers and which tiny results raise Underflow. Five
exceptions are tracked in one unchanging order: Invalid, DivByZero, Overflow,
Underflow, ineXact.

A request reads logb x, or scalbn x n dest mode handling tininess. Blank lines,
hash comments, and anything that fails to parse are passed over in silence.
Each accepted request answers with one line: the result's hexadecimal encoding,
lower case and padded to the width of the format it was delivered in, then the
five character mask of the exceptions signalled. The crate under /app is fed
this stream on standard input; docs states the semantics, data holds worked
samples.
