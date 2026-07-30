Supported finding classes are `signing_key_reuse`, `bearer_forwarding`, `scope_escalation`, `refresh_token_replay`, `audience_confusion`, and `revocation_lag_exposure`.

The analyzer may emit any supported class when evidence satisfies the documented contract. It must never emit a class outside this vocabulary. `rejected_candidates` are not findings and must carry `event_id` plus reason. Findings carry `evidence_event_ids` listing supporting event identifiers.

Finding objects and rejected-candidate objects may include token labels or token evidence fields only in the redacted form defined by `/app/docs/redaction-contract.md`. Raw token fingerprint strings from event payloads must not appear in any published finding or rejected candidate.
