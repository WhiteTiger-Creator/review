# Graph contract

DOT must mirror JSON nodes and edges with deterministic ordering and redacted labels.

## Canonical identifiers

Canonical graph identifiers are graph-safe IDs shared by JSON and DOT. A graph identifier is built from the semantic kind and stable material, then every character outside `[A-Za-z0-9_]` is replaced with `_`. JSON `nodes[*].node_id`, JSON `edges[*].source`, JSON `edges[*].target`, and DOT node identifiers must use this same sanitized identifier.

DOT output must not rely on quoting raw tenant IDs or resource names as node identifiers. Original tenant IDs, request IDs, token labels, and finding labels may appear only in display labels permitted by the relevant contracts. Any token fingerprint label in DOT output must use the `tok_` plus eight-character redaction format from `/app/docs/redaction-contract.md`; raw token fingerprint strings must not appear in DOT node IDs, edge IDs, labels, or attributes.

The DOT edge line uses the same canonical IDs as the JSON edge object:

`<source> -> <target> [label="...", class="..."];`

Nodes and edges are sorted by their canonical IDs.

## Node kinds

The report `nodes` array contains at least these node kinds:

### Chain nodes (`class: "chain"`)

Every distinct tenant-scoped exposure chain in the analyzed corpus must appear as a chain node. Chain nodes carry the resolved correlation key and tenant boundary explicitly:

```json
{
  "node_id": "chain_tenant_a_ex_priority_redact",
  "chain_id": "tenant-a|ex-priority-redact",
  "tenant_id": "tenant-a",
  "trace_id": "tr-lower-priority",
  "label": "tok_fp_gener",
  "class": "chain"
}
```

Requirements:

- `chain_id` is required on chain nodes. It must equal the tenant-scoped chain key from `/app/docs/token-lineage-contract.md` (for example `tenant-a|ex-alpha`, `tenant-b|tr-shared`, or `tenant-a|req-local`).
- `tenant_id` is required on chain nodes and must match the tenant that owns the chain.
- `trace_id` is included when the representative chain event has a trace id. Cross-tenant cases with the same trace id still produce separate chain nodes per tenant.
- `label` uses the redacted token label for the chain when a token fingerprint is known; otherwise it may be empty.
- When both `payload.exchange_id` and `trace_id` are present on chain events, `chain_id` must end with the exchange id, not the trace id.

The same raw token fingerprint in two tenants must produce at least two distinct chain nodes with different `tenant_id` and `chain_id` values. Shared trace ids or request ids across tenants must not collapse into one chain node.

### Finding nodes (`class: "finding"`)

Finding nodes represent exposure classes. They use `node_id` derived from the finding class, include `tenant_id`, and use a redacted `label` when the finding carries token material.

### Tenant nodes (`class: "tenant"`)

Findings without token labels may link directly to a tenant node derived from `tenant_id`.

## Edges

Edges connect findings to chain nodes when a finding has token material, otherwise findings link to tenant nodes. Edge `source`, `target`, and `edge_id` values must use the same canonical node ids as the JSON node objects and must also appear in DOT.
