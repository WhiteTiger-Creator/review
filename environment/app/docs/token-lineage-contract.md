Token-chain correlation is tenant-scoped and uses this priority order:

1. `payload.exchange_id`, when present and non-empty;
2. top-level `trace_id`, when present and non-empty;
3. refresh-family identifier (`payload.refresh_family` or `payload.refresh_family_id`) for refresh-token rotation/replay events, when present;
4. top-level `request_id` as a last-resort local request key.

The tenant id is always part of the chain key. `request_id` alone is never globally unique because tenants and retries may reuse it. If both `payload.exchange_id` and `trace_id` are present, `payload.exchange_id` wins.

Policy code must tolerate events where any optional key is missing, null, or present only in the payload object. Missing optional fields are treated as absent, not as OPA evaluation errors.
