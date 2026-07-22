# Output file format

On success, `svd_solve` writes:

```
m=<m>
n=<n>
status=OK
message=<free text>
singular_values=<s_0> <s_1> ... <s_(n-1)>
U
<m lines of 2n numbers: row i of U, each entry as "re im">
V
<n lines of 2n numbers: row i of V, each entry as "re im">
```

`singular_values` holds the `n` singular values of `A`: real, nonnegative,
and sorted in descending order (`s_0 >= s_1 >= ... >= s_(n-1) >= 0`). `U` is
the complex `m x n` matrix with orthonormal columns and `V` is the complex
`n x n` unitary matrix such that `A = U * diag(singular_values) * V^H` (`^H`
denoting conjugate transpose), with `U`'s and `V`'s columns ordered to match
`singular_values`. Each entry of `U` and `V` is written as its real part
immediately followed by its imaginary part, the same convention used for the
input case file.

On failure (malformed input or a matrix the program cannot factor), it
writes only the first four lines with `status=ERROR` and a `message`
describing the problem, and the program exits with a nonzero status.
