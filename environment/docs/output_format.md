# Output format

The program receives an output path as its second argument and writes one line
per input problem to that path.

Process the input problems in ascending order of file name. For each problem write
a single line that begins with the exact problem file name, then a space, then the
n Lyapunov exponents in decreasing order, separated by single spaces. Print each
exponent with full double precision, for example using the %.17g conversion.

A line therefore looks like

    problem_005.txt lambda_1 lambda_2 ... lambda_n

The paired .expected.txt files in the data directory contain the same
space-separated sequence of exponents, without the leading file name, so they can
be compared directly against the entries of an output line.
