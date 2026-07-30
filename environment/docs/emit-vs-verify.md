# Emit versus verify playthrough paths

A regenerated dossier can look locally consistent and still fail the
independent scoring probe. Soft schedule acceptance is not the win condition;
scoring residual vectors, replay digests, and rule coverage against slice 137 are.

Treat transcript fields (`fuzz_margin_vector`, `obligation_ids_satisfied`,
`replay_digest`, `verify_clean`) as the score sheet for closed-instance acceptance.
Nest-depth continuity, boundary arm coverage, and seal binding must hold together
with closed-instance tolerance tightness and correct save-state merge behavior.
