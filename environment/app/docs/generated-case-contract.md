# Generated verifier case contract

The behavioral verifier synthesizes small NDJSON shards at runtime to exercise public contracts without copying hidden fixture bytes. Deterministic generated identifiers and shard names are:

## Event identifiers

- `gen-ex-a`, `gen-ex-b`, `gen-ex-c`, `gen-ex-d`
- `gen-req-a`, `gen-req-b`
- `gen-null-payload`, `gen-null-trace`, `gen-empty-payload`
- `gen-scope-allow`, `gen-scope-deny`
- `gen-fwd-untrusted`, `gen-fwd-trusted`, `gen-fwd-attempted`, `gen-fwd-blocked`, `gen-fwd-missing`
- `opa-ex`, `opa-scope`, `opa-fwd-miss`, `opa-fwd-att`, `opa-fwd-ok`, `opa-no-payload-key`

## Shard filenames

- `generated-chain.ndjson`
- `generated-scope.ndjson`
- `generated-forward.ndjson`
- `generated-redaction.ndjson`
- `generated-cross-tenant.ndjson`
- `generated-priority-redaction.ndjson`

## Nested scope example

Allowed nested `scope_decision` events may use:

```json
{
  "decision": "allow",
  "required": {"resource_scope": "vault:tenant-b:read"},
  "granted": {"scopes": ["vault:tenant-b:read"]},
  "resource_tenant": "tenant-b"
}
```

Denied nested decisions use `"decision": "deny"` with the same shape and must not produce `scope_escalation`. Only allowed or granted decisions may escalate when the required scope is exactly present and the resource tenant is outside the requesting tenant.

## OPA direct-eval scratch input

Direct OPA regression checks write a temporary JSON document named `opa-eval-input.json` containing legacy and current optional-field shapes plus `trust_boundaries` from `/app/config/trust-boundaries.json`.

## Proxy identifiers

Generated forwarding cases use `proxy-untrusted-1` and `proxy-internal-mesh` from `/app/config/trust-boundaries.json`. Only successful `token_forwarded` events whose `proxy_id` is in `untrusted_proxies` are `bearer_forwarding` findings. `token_forward_attempted` and `egress_blocked` events are rejected candidates with reason `blocked_forward`. A missing `proxy_id` is not exposure.

## Adversarial generated redaction and lineage cases

Generated verifier cases may combine chain-key priority, optional payload shapes, token redaction, cross-tenant isolation, and graph consistency in one synthetic corpus. Implementations must handle these cases with the same contracts used for bundled events.

Additional generated identifiers may include:

- `gen-redact-issue-a`
- `gen-redact-forward-a`
- `gen-redact-revoke-a`
- `gen-redact-lag-use-a`
- `gen-cross-tenant-same-fp-a`
- `gen-cross-tenant-same-fp-b`
- `gen-mixed-chain-exchange`
- `gen-mixed-chain-trace`
- `gen-rejected-fwd-attempt-redact`

Generated token fingerprints may include strings beginning with `fp_generated_`. Examples used by the verifier include `fp_generated_access_alpha_001`, `fp_generated_priority_001`, `fp_generated_priority_rejected_001`, and `fp_generated_shared_cross_tenant_001`. These raw strings must not appear in published JSON or DOT; their display labels use `tok_` plus the first eight characters.

### Cross-tenant fingerprint isolation (`generated-cross-tenant.ndjson`)

The same raw token fingerprint may appear in `tenant-a` and `tenant-b` with the same `trace_id` and `request_id`. Published output must redact the fingerprint, but the graph must still emit separate chain nodes for each tenant. Each chain node needs `chain_id`, `tenant_id`, and a distinct `node_id`; both tenants must be represented.

### Exchange priority with redaction (`generated-priority-redaction.ndjson`)

When `payload.exchange_id` is `ex-priority-redact` and a lower-priority `trace_id` is also present, `chain_id` on chain nodes must end with `ex-priority-redact`, not the trace id. Bearer forwarding and rejected forward attempts in the same exchange must still redact token fingerprints, emit chain nodes for the exchange-scoped key, and record attempted forwards only in `rejected_candidates`.
