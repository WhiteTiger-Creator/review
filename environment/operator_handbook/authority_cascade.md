# Cascaded authority distrust

Distrusting an authority by name has never been meant to stop at that one
certificate. An authority that a distrusted authority brought into existence
inherits the same standing, and so does anything below that, all the way down.
The `distrust_name` table only records where the operators cut; working out what
falls as a result is left to the remediation tooling.

## The subordinate graph

Read every certificate under `authorities/`. Each one that is not self-signed
contributes a directed edge

```
subject CN of its issuer  ->  subject CN of the certificate itself
```

Self-signed roots contribute no edge; an edge from a root to itself would drag
its whole hierarchy into any cascade that touched it.

The graph is over **common names**, not fingerprints. That matters because a
cross-signed authority appears under several certificates with different
fingerprints and different parents, and all of them describe the same authority.
`inter-mesh` in this incident is issued both by `inter-a2` and by `inter-b1`, so
it collects an inbound edge from each.

## The cascade set

Seed the set with every common name in `distrust_name` of the post-migration
store. Then close it: whenever a name in the set has an outbound edge, the name
at the other end joins the set too. Keep going until nothing new appears. An
authority whose common name ends up in the set is **under cascaded distrust**.

Two properties of this graph are worth knowing before you walk it.

It is not a tree. One inbound distrusted parent is enough, so an authority under
cascaded distrust stays that way no matter how many clean parents it also has.
Checking only the parent a particular chain happens to go through gives the
wrong answer.

It contains a cycle. `inter-ring-p` and `inter-ring-q` cross-certify each other,
so following edges without remembering where you have already been does not
terminate. Reaching either one of them puts both in the set.

The seed is post-migration `distrust_name` together with the containment set of
`exposure_containment.md`. Names added by honoured warrants are **not** part of
the seed, so the set is fixed before any warrant is judged and does not depend
on the order warrants are evaluated. The containment set is different in kind: it
is chosen precisely because of what its members carry underneath them, and it is
worked out after the warrants have been judged, so folding it into the seed keeps
the order of work unambiguous. Leaving it out would put the containment at odds
with the certificate decisions, since a subject would be reported as still
validating through a subordinate the containment was chosen to cut.

## Where the cascade is used

Warrant condition 5 in `distrust_warrants.md` rejects an issuer that is under
cascaded distrust, which is why an authority several hops below a distrusted one
cannot quietly authorise new distrust.

Certificate path evaluation in `certificate_validation.md` treats a path member
under cascaded distrust exactly as it treats one named directly in
`distrust_name`: the member is tainted and the path is revoked.

Exposure containment in `exposure_containment.md` cascades a candidate set the
same way when it works out whether a cut reaches every path of a subject.

The cascade does **not** by itself add rows to `remediation.sql`. It changes
which warrants are honoured and which paths are tainted; the rows come from the
honoured warrants and from the containment set.
