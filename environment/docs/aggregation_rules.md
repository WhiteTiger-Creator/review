# Aggregation rules

These rules define the aggregation state of every port. They are the complete
set of rules that decide the report; nothing else affects it.

## Candidacy

A port is a candidate only when it is administratively up, its carrier is up,
and it has a physical peer at the other end of a `LINK`. A port that fails any
of these three conditions is not a candidate.

## Agreement

Advertised partner fields are not authoritative. A candidate port agrees with
its peer when all of the following hold: the port is aggregatable; the peer at
the other end of its `LINK` is itself administratively up and carrier up; the
port's `partner_system_id` equals the `system_id` of the switch that owns that
peer; and the port's `partner_key` equals that peer's `actor_key`.

Agreement is evaluated separately for each port. A port agreeing with its peer
does not by itself say anything about whether that peer agrees back.

## Groups

Agreeing ports on the same switch belong to the same aggregation group when
they share both their `actor_key` and their `partner_system_id`. Ports that
share only one of the two are in different groups. Ports that do not agree
belong to no group.

## Symmetry

A group is symmetric when the peers of its members are themselves all agreeing
ports, those peers all belong to one single group on the peer switch, and that
peer group's member count equals this group's member count. A group that is not
symmetric has formed no aggregation.

## Minimum links

The `min_links` that governs a group is the one on the group's own switch whose
`LagConfig.actor_key` equals the group's `actor_key`. A symmetric group is
compared against that value and no other.

## Resulting state

Every port has exactly one state, decided by the first rule below that applies
to it.

A port that is not a candidate is `Detached`, with `lag_id` `NONE`.

A candidate port that is not aggregatable, or that does not agree with its
peer, or whose group is not symmetric, is `Individual`, with `lag_id` `NONE`.

A port whose group is symmetric and whose group member count is at least the
governing `min_links` is `Bundled`.

Any other port is `Down`.

`Bundled` and `Down` ports both report `lag_id` as the port's `actor_key`, a
colon, and the port's `partner_system_id`, with no spaces.
