# Modification model

For each case the operator under consideration is the base operator plus a symmetric
low rank modification built from the case terms. With base operator A and terms
consisting of weights d_i and dense mode vectors u_i, the modified operator is

    A' = A + sum over i of d_i * u_i * u_i^transpose

The mode vectors are dense, so even a handful of terms makes A' a dense perturbation of
A. The modification is symmetric, and the weights may push eigenvalues up or down.

The reported quantity for a case is the number of eigenvalues of A' that are strictly
less than the case shift. With zero terms this reduces to the number of eigenvalues of
the base operator below the shift.
