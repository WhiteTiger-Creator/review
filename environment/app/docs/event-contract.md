Events are NDJSON with schema_version 2. Stable identity is (collector_id, collector_sequence, event_id). Logical time uses collector offsets from collectors.json and collector_sequence within a collector.

OPA policies must be defensive over optional fields. Payloads in this corpus family may omit optional nested objects, use null for absent ids, or represent semantically equivalent fields in legacy and current shapes documented by the class-specific contracts. Missing optional values must cause the candidate to be ignored or rejected according to the contract, not a policy evaluation error.
