# Input format

The program receives an input directory as its first argument. The directory
holds one or more problem files whose names end in .txt. Files whose names end in
.expected.txt are reference answers for the bundled examples and are not problems
to solve; ignore them when reading the input directory.

Each problem file describes one matrix sequence in plain text. The first line
holds two integers, n and k: the common order of the matrices and the number of
matrices in the sequence. What follows is the sequence M_1, ..., M_k in order,
each matrix written as n lines of n whitespace-separated decimal values in row
major order (so k*n value lines in total after the header). Whitespace and line
breaks beyond this are not significant. The values are written with enough digits
to be read back exactly as double precision floating point.

The bundled examples under the data directory follow exactly this format, and each
is paired with a .expected.txt file giving the exponents that solve it, so an
implementation can be checked against them before submission.
