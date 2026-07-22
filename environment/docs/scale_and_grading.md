# Scale and grading

The operator has on the order of a million degrees of freedom. A dense representation
of the modified operator would need on the order of a million squared entries, so
forming it explicitly or running a dense eigenvalue decomposition is not viable within
ordinary memory and time budgets. The mode vectors are dense, so the modification
cannot be absorbed as a sparse edit either.

Each reported count is a single exact integer. Counts are checked for equality against a
reference computed from the same pinned operator for query cases that are not included
with the toolkit. A count that is off by even one for a case is wrong for that case.

Shifts in the graded cases are chosen away from the immediate neighbourhood of the
spectrum so that the exact count is well defined.
