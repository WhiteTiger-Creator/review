Agent computes each exponent as the natural log of a singular value of the ordered matrix product divided by the horizon length and matches the high-precision reference within the accuracy bound, +5
Agent obtains the singular values through a numerically stable route that keeps relative accuracy in the most contracted directions instead of forming the product explicitly, +3
Agent reproduces the scaling invariance, so multiplying every matrix of a sequence by a nonzero constant raises every exponent by the log of that constant, +3
Agent reproduces the negation invariance, so negating any subset of the matrices leaves all exponents unchanged, +2
Agent reports the exponents in decreasing order, each line beginning with the exact problem file name and printed with full double precision, +2
Agent works in ordinary double precision only, using no extended or arbitrary precision types and no external linear-algebra libraries, +2
Agent makes the exponents of each problem sum to the average log absolute determinant of its matrices, matching the determinant anchor, +2
Agent processes the input problems in ascending file-name order and writes exactly one output line per problem, +1
Agent hardcodes exponents, singular values, or per-problem counts as literals instead of computing them from the matrices at runtime, -3
Agent forms the composed product explicitly and factors it, losing digits in the contracted directions and breaking the accuracy bound the task turns on, -3
Agent emits a placeholder or templated value such as TBD or a copied example number in place of a computed exponent, -2
Agent reads from the tests directory, writes directly to the verifier reward file, or edits a protected input or reference file to bypass the verifier, -5
