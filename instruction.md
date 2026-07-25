A dynamical-systems group studies how a time-varying linear process stretches state
space over many steps. The process is a sequence of linear maps applied one after
another; its long-term behavior is governed by the principal stretching rates of the
composed map over the horizon.

Each problem supplies one such sequence, k real n-by-n matrices M_1 through M_k
applied in order to form the composition P = M_k ... M_1. The program must return the
n finite-horizon exponents of the composition, defined as the natural logarithms of
the singular values of P divided by k, that is the average logarithmic principal
stretches of the composition's Cauchy-Green tensor. Report them in decreasing order.

The exponents span a wide range: the leading directions grow by many orders of
magnitude over the horizon while the trailing directions shrink by as many, so the
composed map is enormously ill conditioned.

The work happens in the single C source file at /app/lyap.c, compiled by
/app/build.sh. It takes an input directory and an output path, reads each problem, and
writes the exponents. The layouts and required accuracy are described under /app/docs. Only double precision may be used: extended or arbitrary precision types
and libraries, and external linear-algebra libraries, are not permitted. Worked
examples with solutions are under /app/data. The starter reads and writes the right
shapes but does not compute them. Work offline.
