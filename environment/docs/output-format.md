# Result encoding

Each result has two space separated fields.

The first column is the hexadecimal encoding of the result, written in lower
case with leading zeros so that it always fills the width of the format the
result was delivered in: 4 digits for `b16`, 8 for `b32`, and 16 for `b64`,
as `destination-formats.md` tabulates. A `logb` result is binary64, so it is
always 16 digits.

The second column is a five character flag mask. The characters appear in a
fixed order that never changes between lines: Invalid, DivByZero, Overflow,
Underflow, ineXact. Each position holds `1` when that exception is signalled
by the operation and `0` when it is not. The mask reports only the exceptions
raised by the single request on its own line; nothing carries between lines.
