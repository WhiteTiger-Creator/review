# Patch records

A case file begins with a single integer giving the number of cases. Each case then
consists of a header line with three fields, the rate shift, the number of conductance
side patch terms and the number of capacitance side patch terms. The conductance side
record follows, then the capacitance side record.

A side record with zero terms occupies no lines at all. A side record with k terms is
k lines each holding one unsigned 64 bit seed, followed by k lines carrying the upper
triangle of that side's k by k coupling block: the first of those lines holds the k
entries of the block's first row starting at the diagonal, the next holds the k minus 1
entries of the second row starting at its diagonal, and so on down to a single entry.

Each seed expands into a dense unit length shape vector through the generator in
`src/vecgen.c`; the same seed always yields the same vector for a given model size.
Collecting a side's k shape vectors as the columns of U and reading its coupling block
as the symmetric matrix W, that side contributes U W U^transpose to its own member of
the pair. So the patched model of a case is the pair

    K + U_cond W_cond U_cond^transpose ,  C + U_cap W_cap U_cap^transpose

Conductance side coupling blocks may be indefinite and their terms may pull rates in
either direction. Capacitance side coupling blocks are positive definite, which keeps
the patched capacitance operator positive definite and every rate of the patched model
real and positive. The shape vectors are dense, so both patched members are dense
perturbations of sparse operators.
