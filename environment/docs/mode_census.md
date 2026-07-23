# Relaxation mode census

A thermal model made of a conductance operator K and a capacitance operator C relaxes
through modes. A mode is a pair of a rate lambda and a non trivial shape x satisfying

    K x = lambda * C x

so the rates of the model are the generalized eigenvalues of the pair. Both members of
the pair are positive definite, so every rate is real and positive.

Each case names one rate shift and asks for its census: the number of modes of that
case's patched model whose rate is strictly less than the shift. The answer is a single
integer. A mode whose rate equals the shift exactly is not counted.

A case with no patch terms on either side is a census of the bare pair K and C. Patch
terms move rates up and down, so the census of a patched case can be larger or smaller
than the bare census at the same shift.
