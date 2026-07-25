# Exception flags

Five exceptions are reported, always in this order.

Invalid signals an operation that has no meaningful result in the reals, such
as a signalling Not a Number operand.

DivByZero signals an exact singular result from a finite operand, delivering a
correctly signed infinity.

Overflow signals a result whose magnitude is too large for the finite range of
the destination format, as IEEE 754-2019 clause 7.4 defines.

Underflow signals a tiny result, as clause 7.5 defines. Which results count as
tiny is settled by the tininess-detection attribute of the request, and under
default handling the condition also requires a loss of accuracy.

ineXact signals that the delivered result differs from the exact mathematical
result, as clause 7.6 defines. An exact result never sets it.

The two range conditions and their companion flags depend on the
exception-handling attribute of the request, which `exception-handling.md`
sets out.
