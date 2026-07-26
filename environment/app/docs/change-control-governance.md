# Harbor relay change-control governance record

Revision CCG-2026.07-4

This record governs authorization of a commissioned relay generation after the operating catalog has resolved the site, route family, socket candidate, and body tier. It is a separate authority plane from the operations catalog. Operators obtain one exact snapshot from `/opt/harbor/change-control.db` by setting `HARBOR_CATALOG_DB` for the existing read-only `catalog-query` interface and using `/app/share/change-control.batch`. The raw database is not an operator interface. The snapshot bytes are authoritative and are normally redirected to a temporary file so terminal display limits cannot truncate the record.

## Ticket selection

At the sealed timestamp, consider only non-disabled tickets whose state is exactly `APPROVED`, whose site alias, incident code, and route family match the already resolved commissioning state, and whose inclusive authorization window contains the sealed timestamp. Among eligible tickets, later `source_epoch` outranks `precedence_rank`; rank is consulted only when source epochs tie. An unresolved tie fails commissioning. Ticket state, window, family, and alias are independent gates, so a later HOLD ticket or a high-ranked ticket for an older family cannot authorize the generation.

## Approval state and quorum

For each approver and role on the selected ticket, retain the last event at or before the sealed timestamp. Later event epoch outranks event precedence; precedence is used only for events at the same epoch. `approve` and `reinstate` produce an effective approved state. `revoke` produces an effective revoked state until a later valid reinstatement. Future events are invisible.

Approved records are then grouped by the role's `exclusive_group`. One record per group contributes to quorum. Within a group, select the record with the greatest role weight; ties use later effective event epoch and then lexicographically smaller approver ID. Quorum is the sum of the selected records' integer weights. It must meet the ticket's `quorum_required`, and at least two distinct exclusive groups must contribute. Non-contributing approved records remain part of the decision evidence but are not serialized as effective approvals.

For the sealed window, the effective approval serialization is ordered by exclusive group and then approver ID. Each member line is exactly `exclusive_group|approver_id|role_code|weight|state|event_id\n`. The final newline is included. `state` is the effective event kind, so a reinstated approval serializes as `reinstate`, not `approve`.

## Activation candidate

An activation candidate is eligible only when it belongs to the selected ticket, is enabled, is effective at the sealed timestamp, names the selected operations-catalog socket candidate, and names the exact selected body-tier code. Among eligible candidates, later `source_epoch` outranks precedence rank. An unresolved tie fails. The release lane is taken from the selected activation candidate.

## Authorization seal

`/app/var/activation-seal.json` is compact UTF-8 JSON followed by exactly one newline. It has these top-level keys in order: `ticket_id`, `change_generation`, `activation_id`, `release_lane`, `quorum_required`, `quorum_observed`, `approvals`, `authorization_digest`, `activation_token`.

The `approvals` array contains only the effective quorum-contributing records. Each object has keys in this order: `exclusive_group`, `approver_id`, `role_code`, `weight`, `state`, `event_id`. `weight` is a JSON integer. The authorization digest is SHA-256 over the exact member lines defined above. The 24-character activation token is the leading lowercase hexadecimal portion of SHA-256 over the UTF-8 bytes of `ticket_id|activation_id|authorization_digest|run_id`, with no trailing newline.

The seal is generation content with mode `0640`. Its real SHA-256 and byte count appear in both publication inventories. The deployment manifest includes an `authorization` object equal to the seal object. The seal itself does not contain the deployment manifest digest, avoiding recursive identity.
