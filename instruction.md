An IEEE 754-2019 conformance task: compute the operations logb and scalbn and
the flags each raises. logb returns the radix two exponent of its
binary64 operand in that format. scalbn returns its operand multiplied by two
raised to a given integer power n, with the exact product mapped in one step
into the interchange format the request names, binary16, binary32, or binary64,
under three attributes it also names: one of the five rounding directions; an
exception handling, either the default or the exponent adjusted alternate
handling of clause 8.2; and a tininess detection, before or after rounding.
Operands are 16 character hexadecimal strings giving all 64 bits. The demanding
corners are signed zeros, infinities, quiet and signalling Not a Number
operands, and each destination's subnormal and exponent range edges, where the
attributes decide what an overflow delivers and which conditions a tiny result
raises. Bits and flags must both be exact. Five exceptions are tracked, always
in this order: Invalid, DivByZero, Overflow, Underflow, ineXact.

A request is logb with an operand, or scalbn with an operand, a signed decimal
scale n, a destination token, and the three attributes. Blank lines, hash
comments, and unmatched lines are ignored. Every accepted request yields one
result line: the hexadecimal encoding of the result in its destination format,
lower case with leading zeros, then a five character flag mask whose positions
are 1 for the exceptions signalled. Complete the Rust crate in /app so cargo
build --release produces /app/target/release/fpexp, reading requests on
standard input.
