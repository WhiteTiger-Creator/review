# Case file format

Every file matching `data/case_*.txt` holds one case: a dense complex `m x n`
matrix `A` with `m >= n`, no other structure implied by the file format
(some cases happen to be sparse or banded, but the reader must not assume
this).

```
m n
re(a_00) im(a_00) re(a_01) im(a_01) ... re(a_0(n-1)) im(a_0(n-1))
re(a_10) im(a_10) re(a_11) im(a_11) ... re(a_1(n-1)) im(a_1(n-1))
...
re(a_(m-1)0) im(a_(m-1)0) ... re(a_(m-1)(n-1)) im(a_(m-1)(n-1))
```

The first line holds the two integers `m` and `n` separated by whitespace.
Each of the next `m` lines holds `2n` whitespace-separated floating-point
numbers: row `i` of `A`, with each entry `a_ij` written as its real part
immediately followed by its imaginary part (an entry with zero imaginary
part is still written as two numbers, e.g. `1.5 0.0`). Blank lines are not
present in a well-formed case file, and no other content (comments, headers)
appears.
