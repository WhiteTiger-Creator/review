# Maintenance-window allocation record

Revision MW-2026.07-4

This record governs the scheduled service window after the operating catalog has resolved the site, route family, socket allocation, and body tier. The maintenance catalog is read through `/app/bin/catalog-query` with `HARBOR_CATALOG_DB=/opt/harbor/maintenance-window.db` and `/app/share/maintenance-window.batch`. The exact stdout stream is the authoritative snapshot.

## Maintenance order

At the sealed timestamp, an order is eligible only when it is enabled, has state `SCHEDULED`, matches the resolved site alias, service class, and route family, and contains the timestamp in its inclusive window. Later `source_epoch` wins; `precedence_rank` breaks only equal source epochs. An unresolved tie is invalid.

## Operator acknowledgments

For each operator and role on the selected order, retain the latest event at or before the sealed timestamp. Event time wins, then precedence rank, then event ID. `acknowledge` and `restore` are effective; `withdraw` is not. Effective records are grouped by `work_group`. One record per group contributes: greatest role weight, then latest event time, then lexicographically smaller operator ID. The sum must meet `ack_weight_required`, with at least two contributing groups.

The contributing records are sorted by `work_group`, then `operator_id`. Each digest member is exactly `work_group|operator_id|role_code|weight|state|event_id\n`; the final newline is included. The SHA-256 of those member lines is `readiness_digest`.

## Service slot and window plan

A service slot is eligible only when it belongs to the selected order, is enabled and effective at the sealed timestamp, and names the selected socket candidate and exact body-tier code. Later `source_epoch` wins; rank breaks only equal epochs.

`/app/var/window-plan.json` is compact UTF-8 JSON followed by one newline. Keys are ordered: `order_id`, `schedule_generation`, `slot_id`, `service_lane`, `ack_weight_required`, `ack_weight_observed`, `acknowledgments`, `readiness_digest`, `launch_token`. Each acknowledgment object is ordered: `work_group`, `operator_id`, `role_code`, `weight`, `state`, `event_id`. `launch_token` is the first 24 lowercase hex characters of SHA-256 over `order_id|slot_id|readiness_digest|run_id` with no newline.
