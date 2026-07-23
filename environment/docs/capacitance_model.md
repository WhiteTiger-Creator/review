# Capacitance operator

A relaxation census needs both members of the thermal pair. Only the conductance
operator K is distributed; the capacitance operator C is defined from it and is not
stored anywhere.

C is symmetric and carries the same sparsity pattern as K. Its off diagonal entries are
the magnitudes of the corresponding conductance entries,

    C_ij = |K_ij|   for i not equal to j

and each diagonal entry is the sum of the magnitudes of every entry in that row of the
conductance operator,

    C_ii = sum over j of |K_ij|

where j runs over the entire row of K, including the diagonal position j equal to i.

Because every diagonal entry of K is positive, C is symmetric with strictly dominant
positive diagonal, so C is positive definite. This is the usual absolute row lumping
used to give a conductance model a consistent thermal mass; it is a property of the
operator alone and does not depend on the case.
