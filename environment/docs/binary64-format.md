# binary64 encoding

A binary64 datum occupies 64 bits: one sign bit, an 11 bit biased exponent
field, and a 52 bit trailing significand field. The exponent bias is 1023.

When the exponent field is between 1 and 2046 the datum is normal and its
numeric value is the significand with an implicit leading one bit, scaled by
two to the power of the field minus 1023.

When the exponent field is 0 and the trailing significand is non zero the
datum is subnormal. A subnormal has no implicit leading one bit; its value is
the trailing significand scaled by two to the power of the minimum normal
exponent minus 52.

When the exponent field is 0 and the trailing significand is 0 the datum is a
signed zero. When the exponent field is 2047 and the trailing significand is
0 the datum is a signed infinity. When the exponent field is 2047 and the
trailing significand is non zero the datum is Not a Number; the most
significant trailing bit distinguishes quiet from signalling.
