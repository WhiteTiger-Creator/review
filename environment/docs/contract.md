# Computational contract

Each problem gives an ordered sequence of k real n-by-n matrices M_1, ..., M_k.
They define a discrete linear cocycle: the ordered product
P = M_k M_{k-1} ... M_1 (with M_1 applied first) expands and contracts space at
different rates along different directions.

Definition (this fixes a unique value at the finite horizon k). Let
sigma_1 >= sigma_2 >= ... >= sigma_n > 0 be the singular values of the ordered
product P. The n finite-horizon exponents are the average logarithmic principal
stretching rates of the cocycle over the horizon,
lambda_i = (1/k) * log(sigma_i), one per principal axis of the Cauchy-Green
tensor P^T P. Report them in decreasing order, lambda_1 >= ... >= lambda_n. These
are canonical singular values of the composed map, not of any single M_t, and are
independent of how the product is evaluated.

Grading. Each returned exponent must match an independently computed reference
within an absolute tolerance of 1e-8. The reference is computed in high precision.
As a consistency anchor, the sum of the exponents equals
(1/k) * sum_t log|det M_t|, because the product of the singular values of P is
|det P|.

Scope of grading. Grading is not limited to the bundled examples: the program is
run on many additional held-out problems that span a wide range of magnitudes, and
the same 1e-8 accuracy bound applies uniformly to every exponent of every problem,
including the smallest (most contracted) directions, whose singular values may be
tens of orders of magnitude below the largest.

Invariances. Because the exponents are (1/k) log of the singular values of the
ordered product, they obey two exact identities, and the grader checks that your
program reproduces each to the tolerance above on additional problems:
multiplying every matrix of a sequence by a nonzero constant c raises every
exponent by log|c| (each singular value of P scales by |c|^k), and negating any
subset of the matrices leaves all exponents unchanged. These follow from the
definition and are checked to the tolerance above on additional problems.

Restrictions. Work in ordinary double precision. Extended or arbitrary precision
numeric types and libraries, and external linear-algebra libraries, are not
permitted; the source is checked and the problem is failed if any appear. Every
reported exponent must be finite.
