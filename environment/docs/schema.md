# Input and output schema

## Input

One instance is read from the file whose path is the program's single argument.

The first line holds two integers `d n`, the degree and the number of terms.
Each of the next `n` lines holds four integers `i j k c`, standing for the
monomial `c * x^i * y^j * z^k`. The polynomial is the sum of these terms, a
homogeneous form of degree `d` in the three variables `x`, `y`, `z` with integer
coefficients, defining a curve in the projective plane.

The degree satisfies `3 <= d <= 4`. There are `n >= 1` terms. Every exponent
triple satisfies `i, j, k >= 0` and `i + j + k = d`. Every coefficient satisfies
`c != 0` and `|c| <= 1000000`. No monomial appears twice.

Integer tokens are strict: an optional single leading `-` followed by one or
more decimal digits, with no leading zero unless the token is the literal `0`;
`-0`, `+3`, and `07` are not well formed. Tokens on a line are separated by a
single space, with no leading or trailing space and no run of two or more
spaces. The file ends with exactly one trailing newline and contains exactly
`n + 1` lines.

Any violation of this grammar, a term count that disagrees with `n`, a degree
outside the range, an exponent triple whose sum is not `d`, a repeated monomial,
an out-of-range or zero coefficient, or a missing or extra newline or line makes
the input malformed, and the only correct output is `ERROR`.

## Domain

The census is defined only for a reduced curve every one of whose singular
points, taken over the complex projective plane, is a rational point that is
either an ordinary double point (two smooth branches meeting transversally, with
two distinct tangent directions) or an ordinary cusp (a single cuspidal branch).
A curve with any other singularity, a singular point that is not rational, a
repeated component, or a straight-line component lies outside the domain, and the
correct output is `ERROR`. Singular points at infinity count exactly as those in
the finite plane.

The output contract and the seven reported quantities are in
[OUTPUT-CONTRACT.md](OUTPUT-CONTRACT.md).
