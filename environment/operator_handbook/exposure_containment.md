# Containing an exposure

Incident EXP-7741 arrived with a list of subjects rather than a list of
authorities. Some of them are known to be in the wrong hands and must stop
validating; one of them carries traffic the business will not agree to drop.
Turning that list into trust-store rows is the remediation tooling's job, and
the operators care how large the answer is: every authority added to
`distrust_name` invalidates certificates nobody has inventoried yet, so the cut
has to be as small as the constraints allow.

## The incident list

`exposure.tsv` is tab separated with a header row and three columns, `incident`,
`subject` and `disposition`. Each `subject` is the common name of a leaf under
`leaves/`. The `disposition` is either `contain` or `preserve`. Every subject
named in the file appears exactly once.

## Compromised leaves from the signing journal

`signing_journal_reconcile.md` defines how `SIGN` lines join custodian roster
terms. A leaf whose fingerprint has any `out_of_window` reconciled event is
**compromised**. Compromised leaves enter the containment search as additional
`contain` subjects, regardless of their `exposure.tsv` disposition. Reconcile the
entire journal corpus, including any held-out shard grading supplies, before
choosing the containment set; partial reconciliation silently under-cuts.

## What a containment has to achieve

You are choosing a set of authority common names to add to `distrust_name`. Call
it the containment set. Cascade it the way `authority_cascade.md` describes, seed
included, because distrust of an authority reaches everything it certified.

Both conditions are stated in terms of a subject's **live** paths. A path is
live when it is anchored, meaning it ends at a fingerprint in `trusted_roots` as
`certificate_validation.md` requires; when no member of it is already distrusted
in the store as it stands after the migration and after the honoured warrants
have been applied; and when it would be accepted on its own merits, so not
expired, not yet to become valid, and not in breach of a name constraint. A path
that fails any of those was not carrying the subject before the incident and
does not need cutting now.

A `contain` subject is contained when **every** live path it has runs through at
least one member of the cascaded containment set. A subject with two live paths
is not contained by cutting one of them.

A `preserve` subject is preserved when **at least one** of its live paths comes
through untouched, meaning no member of that path is in the cascaded containment
set. A subject with no live paths at all cannot be preserved.

## Choosing between the sets that work

Many containment sets satisfy both conditions, and they are not equally good.
The one to write down is the **smallest**. Where several sets are the same
smallest size, sort each candidate set by common name and take the one that
comes first in that ordering, comparing name by name.

This is not the set you get by walking the `contain` subjects and distrusting
whichever authority issued each one. It is also not the set you get by taking
the first small answer you find. Both of those produce something that satisfies
the two conditions on this incident while being either larger than necessary or
not the first in order among the smallest.

Candidates are the common names of authorities under `authorities/`. A leaf's
own common name is never a candidate, and neither is anything that is not an
authority in the incident bundle.

## Where the answer goes

The containment set is part of the remediation. Each of its names becomes an
`INSERT OR IGNORE` into `distrust_name` in `remediation.sql`, carrying the source
`exposure_containment` rather than the `warrant_honored` the warrant rows use.
These statements follow the warrant statements, in common-name order.

Because the rows land in the store, they are in force for
`certificate_decisions.tsv`. A contained subject is reported `revoked`, with its
tainted members populated the way `certificate_validation.md` describes; a
preserved subject is reported `accepted`. The receipt records the set as well,
so the size of the cut is auditable without reading the patch.
