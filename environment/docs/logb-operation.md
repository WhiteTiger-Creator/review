# logb

`logb(x)` returns the exponent of `x` as a radix two floating point value of
the same format, that is, the exponent e such that the magnitude of `x` lies
between two to the power e inclusive and two to the power e plus one
exclusive.

The result is an integral value delivered in binary64. For a zero operand the
operation is singular. For an infinite operand the result is a positive
infinity. A Not a Number operand is carried through to the result; a
signalling operand is handled as the standard requires for signalling inputs.

The exponent of a finite non zero operand is always representable, so no
inexact, overflow, or underflow condition arises from `logb`.
