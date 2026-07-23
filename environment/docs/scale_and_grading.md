# Scale and grading

The model has on the order of a million degrees of freedom. A dense representation of
either patched member would need on the order of a million squared entries, so forming
one explicitly is not viable within ordinary memory and time budgets. The shape vectors
are dense, so a patch is not a sparse edit either.

Each reported census is a single exact integer. Censuses are checked for equality
against a reference computed from the same pinned operator for cases that are not
included with the toolkit. A census that is off by even one for a case is wrong for that
case.

Rate shifts in the graded cases are chosen away from the immediate neighbourhood of the
spectrum so that the exact census is well defined. The whole graded run is expected to
complete well inside a wall clock budget that a dense method could not meet.
