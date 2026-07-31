# Output contract

For a curve inside the domain, print exactly seven lines, in this fixed order,
each `label = value` with a single space on either side of the equals sign, and a
single trailing newline after the last line:

```
degree = D
class = M
inflections = I
doublepoints = P
cusps = C
crunodes = X
realmeet = R
```

- `degree` (`D`): the degree of the form.
- `class` (`M`): the number of lines of the plane, through a point in general
  position, that are tangent to the curve.
- `inflections` (`I`): the number of inflection points, the smooth points where
  the tangent line meets the curve with contact of order at least three, each
  counted with its multiplicity.
- `doublepoints` (`P`): the number of ordinary double points of the curve, taken
  over the complex projective plane, including any at infinity.
- `cusps` (`C`): the number of ordinary cusps, taken the same way.
- `crunodes` (`X`): the number of those ordinary double points at which the two
  branches of the curve are real, equivalently the two tangents there are real
  and distinct. The remaining double points are the ones whose two tangents form
  a complex-conjugate pair. `X` is at most `P`.
- `realmeet` (`R`): the number of distinct real points, taken in the real
  projective plane, at which the curve meets the line `z = 0`.

Every value is an exact integer and there is no tolerance; two integers are equal
only when they are exactly equal.

If the input is malformed or the curve lies outside the domain described in
[SCHEMA.md](SCHEMA.md), print the single word `ERROR` on one line and nothing
else.
