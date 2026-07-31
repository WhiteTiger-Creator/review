# GraphRun pipeline public contract

This document is the authoritative, agent-visible specification for GraphRun pipeline behavior: graph/run canonicalization, digest rendering, MLflow callback intake, and schema-valid artifact emission. Operational lineage, approval rosters, supersession tables, and incident context live in `/app/docs/graph-run-signer-operations-manual.md`. Implementations must satisfy both documents; where policy recovery or active-key selection details are not repeated here, consult the operations manual.

---

## 1. Policy recovery

The active signing policy file `config/signing-policy.yaml` may be absent from the working tree. Before accepting callbacks or producing attestations, the service must recover an authorized policy from **local Git history only** (no network, no bundled permissive fallback).

### 1.1 Candidate enumeration

Enumerate every commit that ever introduced or modified `config/signing-policy.yaml` by searching:

- All reflog entries reachable from the repository
- Unreachable objects preserved in the local object database (dangling commits, deleted refs, forensic refs)

Each distinct commit that contains a blob at `config/signing-policy.yaml` is a **candidate**. Deduplicate by commit ID.

### 1.2 Authorization criteria

A candidate is **authorized** if and only if **all** of the following hold:

1. **Policy version** — The recovered YAML's `policy_version` field equals the current production version from the operations manual (**2026.1**).
2. **Approval trailer** — The candidate commit message contains an `Approved-By:` trailer naming a principal listed on the **2026.1** approval roster in the operations manual.
3. **Approval window** — The candidate's **committer timestamp** (UTC) falls inside the inclusive **2026.1** approval window bounds defined in the operations manual.
4. **Not superseded** — The policy version is not listed as superseded in the operations manual's policy version history table. Versions superseded before **2026.1** (for example emergency **2025.12**) are never authorized for production attestations after their supersession effective instant.

Recency alone is **never** sufficient. A newer commit that fails any criterion above is unauthorized even if it is the most recent candidate.

### 1.3 Recovery outcomes

| Outcome | Behavior |
|---|---|
| Exactly one authorized candidate | Restore `config/signing-policy.yaml` from that commit's tree. Record the Git commit ID (40 lowercase hex characters) as `policy_commit_id` for all subsequent signing. |
| Zero authorized candidates | **Fail closed.** HTTP **503** on API startup or signing requests; CLI exits non-zero. Do **not** use any built-in permissive fallback. |
| Two or more equally authorized candidates | **Fail closed** as **ambiguous.** HTTP **503** / exit non-zero. Operators must resolve ambiguity out of band; the service must not guess. |

After successful recovery, the restored policy file must be **written to the working-tree path** `config/signing-policy.yaml` (i.e. `/app/pkg/config/signing-policy.yaml` on disk) and must remain there for the lifetime of the process as the sole source of signing policy for attestations. Recovering the YAML only into memory, without creating that on-disk file, is insufficient.

---

## 2. Policy YAML schema

Recovered policy documents must conform to this structure:

```yaml
policy_version: "2026.1"
approval_required: true
attestation_schema_version: "1"
allowed_signing_keys:
  - signer-2025
  - signer-2026
domains:
  graph: GRAPHRUN.GRAPH.v1
  run: GRAPHRUN.RUN.v1
  callback: GRAPHRUN.CALLBACK.v1
  attestation: GRAPHRUN.ATTEST.v1
signing:
  keys:
    - key_id: signer-2025
      private_key_path: /data/keys/signer-2025.pk8
      public_key_path: /data/keys/signer-2025.pub
      not_before: "2025-01-01T00:00:00Z"
      not_after: "2026-01-01T00:00:00Z"
      status: active
    - key_id: signer-2026
      private_key_path: /data/keys/signer-2026.pk8
      public_key_path: /data/keys/signer-2026.pub
      not_before: "2026-01-01T00:00:00Z"
      not_after: "2027-01-01T00:00:00Z"
      status: active
```

### 2.1 Required top-level fields

| Field | Type | Description |
|---|---|---|
| `policy_version` | string | Semantic version of the policy document (must match operations manual production version). |
| `approval_required` | boolean | When `true`, policy recovery authorization rules apply. |
| `attestation_schema_version` | string | Version of the attestation output schema (currently `"1"`). |
| `allowed_signing_keys` | array of strings | Key IDs permitted for signing. |
| `domains` | object | Domain separators for canonical byte framing (see §5–§7). |
| `signing.keys` | array | Key material descriptors (see below). |

### 2.2 Key descriptor fields

Each entry under `signing.keys` must include:

| Field | Description |
|---|---|
| `key_id` | Stable identifier referenced in attestations. |
| `private_key_path` | Absolute path to PKCS#8 Ed25519 private key bytes. |
| `public_key_path` | Absolute path to raw 32-byte Ed25519 public key. |
| `not_before` | ISO-8601 UTC instant; key is valid at `t` when `not_before <= t`. |
| `not_after` | ISO-8601 UTC instant; key is valid at `t` when `t < not_after` (half-open interval `[not_before, not_after)`). |
| `status` | `active` or `revoked`. |

### 2.3 Key selection

At signing time, select the **unique** key where:

- `status` is `active`
- `key_id` is listed in `allowed_signing_keys`
- The run's `started_at` instant falls inside `[not_before, not_after)`

If zero keys match, or more than one key matches, **fail closed** (HTTP **503** or **422** with a structured error; no attestation produced). Revoked keys, disallowed key IDs, and keys outside the temporal window must never be used.

Key rotation overlap rules are defined in the operations manual; the selector must still yield exactly one key or fail.

---

## 3. Graph schema and canonicalization

### 3.1 Input schema

Graph fixtures are JSON objects with:

| Field | Type | Required | Notes |
|---|---|---|---|
| `graph_id` | string | yes | Stable graph identifier. |
| `graph_type` | string | yes | Exactly `"directed"` or `"undirected"`. Do **not** use a boolean `directed` field, a numeric/string `version` field, or any synonym in the framed digest. |
| `nodes` | array | yes | Each element: `{ "id": "<string>" }`. |
| `edges` | array | yes | Each element: `{ "source", "target", "kind"?, "weight"?, "attributes"? }`. |

**Unlisted fields** (for example `layout`, `metadata`, `description`, boolean `directed`, or `version`) are **ignored** for canonicalization and signing. They must not appear in canonical bytes.

### 3.2 Node ID normalization

- Node IDs are case-sensitive Unicode strings.
- Normalize each node ID to Unicode **NFC** before hashing.
- Collect unique NFC node IDs; duplicates after normalization collapse to one entry.

### 3.3 Edge normalization

**Directed graphs** — Preserve `source` → `target` direction.

**Undirected graphs** — Before forming the canonical edge record, order the two endpoints by **UTF-8 byte lexicographic order** of their NFC-normalized IDs. The smaller endpoint becomes `source` and the larger becomes `target` in the canonical record.

**Kind default** — When `kind` is absent, treat it as the empty string `""` in the edge record.

**Weight default and normalization** — When `weight` is absent, treat it as `"0"` (not `"1"`). Otherwise `weight` is a decimal string. Normalize with **Python `decimal.Decimal` semantics** (parity target in §3.6): parse with `Decimal(value)`, call `.normalize()`, render with `format(..., "f")`, then strip trailing zeros after `.` and a trailing `.` (empty result → `"0"`). Emitting the raw input string is **non-compliant**. Concrete outcomes implementations must match:

- `"1.0"` → `"1"` (not `"1.0"`)
- `"1.00"` → `"1"`
- `"01.0"` → `"1"`
- `"1.50"` / `"01.5"` → `"1.5"`
- `"0.5"` / `".5"` → `"0.5"`
- Distinct significant values remain distinct (`"2.0"` → `"2"` ≠ `"2.1"`)

**Attributes** — The input JSON object key is exactly `"attributes"`. When present, `attributes` is an object: sort its keys lexicographically and serialize as **canonical JSON** (UTF-8, no insignificant whitespace, object keys sorted, arrays preserve order). When `attributes` is absent, the fifth NUL-delimited slot of the edge record (`attrs_json`) is the empty string.

`attrs_json` is **only** the name of that framed-record slot — it is **not** an input field name. Implementations must read `edge["attributes"]`. Ignoring that input key (or reading a synonym) leaves `attrs_json` empty and diverges from fixture digests such as `/data/runs/visible-run-a/graph.json` (required digest prefix `2fd15541…`).

**Duplicate collapse** — Edges that are semantically identical after normalization (same endpoints, kind, normalized weight, and canonical attributes JSON) collapse to one edge. Parallel edges that differ in `kind`, normalized `weight`, or `attributes` remain distinct.

### 3.4 Canonical bytes

All string fields are UTF-8. Framing uses **big-endian uint32 length prefix** followed by raw bytes for each field, in order:

1. Domain separator: `GRAPHRUN.GRAPH.v1`
2. `graph_id` (its own length-prefixed field)
3. `graph_type` (its own length-prefixed field)
4. Sorted unique NFC node IDs, joined by newline (`\n`), as **exactly one** length-prefixed field. If there are zero nodes, this field is empty (length 0). Never emit one length-prefixed field per node.
5. For each canonical edge, one record string: `source\0target\0kind\0weight\0attrs_json` where separators are literal NUL bytes (`\0`), `weight` is the Decimal-normalized string from §3.3 (for example `"01.0"` → `"1"`), and `attrs_json` is the canonical JSON of the input key `"attributes"` or the empty string when that key is absent. Sort edge record strings lexicographically by the full record string (UTF-8 byte order of the full record). Emit each sorted record as its **own** length-prefixed field (field 5 is repeated once per edge — N distinct edge records ⇒ N separate framed fields after the nodes field). Do **not** join all edge records into a single framed field with `\n` (or any other delimiter). Do **not** encode edges as JSON objects/arrays in the framed digest.

**Graph digest** = SHA-256 of the concatenated framed bytes, rendered as exactly **64 lowercase hex characters**. Do **not** include a `sha256:` prefix, uppercase hex, or any other scheme/wrapper. Callback payloads and output JSON must carry this bare hex form (see also `/app/docs/signing-manifest.schema.json` and the callback schema pattern `^[a-f0-9]{64}$`).

### 3.5 Local reference vector (self-check)

Implementations may validate §3 framing locally against this minimal fixture (unlisted fields ignored; undirected endpoint reorder + weight normalization collapse the two edge inputs to one record):

```json
{
  "graph_id": "ref-g1",
  "graph_type": "undirected",
  "nodes": [{"id": "b"}, {"id": "a"}],
  "edges": [
    {"source": "b", "target": "a", "kind": "data", "weight": "1.50"},
    {"source": "a", "target": "b", "kind": "data", "weight": "01.5"}
  ],
  "layout": {"ignored": true}
}
```

Expected `graph_digest` (bare lowercase hex): `30ffcf0c24513d17b347893f4765c62dfc37888098e86da433d497f79a41f255`.

**Worked field list for `ref-g1`** (each numbered item is **exactly one** big-endian uint32 length-prefixed UTF-8 field; `\n` is a literal newline; `\0` is a literal NUL). After NFC + sort, nodes are `a` then `b`. Undirected endpoint reorder + weight normalization (`1.50` / `01.5` → `1.5`) collapse the two input edges to one record with `source=a`, `target=b`:

1. `GRAPHRUN.GRAPH.v1`
2. `ref-g1` (`graph_id` — its own top-level field)
3. `undirected` (`graph_type` — its own top-level field)
4. `a\nb` — **one** field: sorted unique NFC node IDs joined by a single `\n` (UTF-8 length **3**). Do **not** emit `a` and `b` as two separate length-prefixed fields.
5. `a\0b\0data\01.5\0` — **one** field: the NUL-delimited edge record `source\0target\0kind\0weight\0attrs_json` (here empty `attrs_json`). Do **not** serialize the edge as a JSON object / JSON array text. When multiple distinct edge records remain after collapse, repeat this step once per sorted record (each record its own length-prefixed field).

Hashing the framed concatenation of those five fields must yield `30ffcf0c24513d17b347893f4765c62dfc37888098e86da433d497f79a41f255`.

A directed graph that omits `weight` on a self-edge must treat weight as `"0"`. For `graph_id` `ref-g2`, `graph_type` `directed`, nodes `[{"id":"n1"}]`, edges `[{"source":"n1","target":"n1"}]`, expected digest: `1cd1c759d95e140e8bb6c9fd583ef5474f2ee220763038597c934ee5cb031017`.

**Worked field list for `ref-g2`** (same framing rules; `\0` denotes a literal NUL byte):

1. `GRAPHRUN.GRAPH.v1`
2. `ref-g2`
3. `directed`
4. `n1` (sorted unique node IDs joined by `\n`; here a single node — still **one** field, not per-node framing)
5. edge record `source\0target\0kind\0weight\0attrs_json` = `n1` + `\0` + `n1` + `\0` + `` + `\0` + `0` + `\0` + `` (empty `kind`, weight `"0"`, empty `attrs_json`). This single edge is its **own** length-prefixed field — do not concatenate multiple edge records into one framed field, and do not encode edges as JSON text.

Hashing the framed concatenation of those five fields must yield the gold digest above.

**Multi-edge framing is normative (do not rely on single-edge self-checks alone).** `ref-g1` / `ref-g2` each leave only one edge record after collapse, so joining edges into one field can still match those digests by accident. A directed graph with **two** distinct edge records exposes the framing rule. For `graph_id` `ref-g3`, `graph_type` `directed`, nodes `[{"id":"n2"},{"id":"n1"}]`, edges `[{"source":"n1","target":"n2","kind":"data","weight":"1"},{"source":"n2","target":"n1","kind":"ctrl","weight":"2.0"}]`, expected digest: `f5e3aa02c56b6216b1913848661a952fc7dcd16d1af2259407506f465805cf62`.

**Worked field list for `ref-g3`** (six length-prefixed fields — two separate edge fields):

1. `GRAPHRUN.GRAPH.v1`
2. `ref-g3`
3. `directed`
4. `n1\nn2` — **one** nodes field (UTF-8 length **5**)
5. `n1\0n2\0data\01\0` — first sorted edge record as its **own** length-prefixed field (UTF-8 length **13**)
6. `n2\0n1\0ctrl\02\0` — second sorted edge record as its **own** length-prefixed field (UTF-8 length **13**; weight `"2.0"` → `"2"`)

Any framing that collapses those two edge records into fewer than six length-prefixed fields is **non-compliant**.

**Attributes key + Decimal weight on `/data/runs/visible-run-a/graph.json`.** That fixture has two edges with input key `"attributes"` and weights `"1.50"` / `"01.0"`. After NFC, undirected endpoint order, Decimal weight normalization, and per-edge framing, the sorted edge records (each its own length-prefixed field after the nodes field) are:

- `n1\0n2\0data\01.5\0{"lane":"primary"}` — weight `"1.50"` → `"1.5"`; `attrs_json` from `"attributes"`
- `n2\0n3\0data\01\0{"lane":"secondary"}` — weight `"01.0"` → `"1"` (not `"01.0"` / `"1.0"`)

Expected `graph_digest`: `2fd15541530fc3aca6a610b482ac92067ce61baeaa36452ea19bcb84bc8635c9`.

Self-check against the §3.5 worked field lists and gold digests before treating digests as fixed.

### 3.6 Java-oriented framing reference (byte parity)

Verifier digests are computed by an independent helper that length-prefix-frames UTF-8 fields. A Java implementation must emit **identical bytes** for the same fixture (self-check against §3.5 before relying on the full verifier). Normative sketch:

```text
frame(fields):
  out = empty byte buffer
  for each field string f in fields:
    b = UTF-8 bytes of f
    append big-endian uint32 length(b)
    append b
  return out

normalizeWeight(raw):
  value = trim(raw); if empty -> "0"
  if value starts with "." -> prepend "0"
  // REQUIRED parity: Python decimal.Decimal(value).normalize() then format(..., "f"),
  // then strip trailing zeros after '.' and a trailing '.'; empty -> "0".
  // Examples: "1.0"->"1", "01.0"->"1", "1.50"->"1.5". Do not emit the raw input string.
  // In Java, BigDecimal(value).stripTrailingZeros().toPlainString() is acceptable
  // only when it matches the §3.5 gold digests (including visible-run-a) for the same inputs.

graphDigest(graph):
  undirected = (graph.graph_type == "undirected")
  nodes = sorted unique NFC(node.id)   // Unicode code-point / String order
  edgeRecords = empty set of strings
  for each edge:
    source = NFC(edge.source); target = NFC(edge.target)
    if undirected and UTF-8(source) > UTF-8(target): swap source, target
    kind = edge.kind if present else ""
    weight = normalizeWeight(edge.weight if present else "0")
    // Input JSON key is "attributes". attrs_json is only the framed slot name.
    attrs_json = "" if edge.attributes absent
                 else compact JSON of edge.attributes with object keys sorted (no insignificant whitespace)
    edgeRecords.add(source + '\0' + target + '\0' + kind + '\0' + weight + '\0' + attrs_json)
  fields = [
    "GRAPHRUN.GRAPH.v1",
    graph.graph_id,
    graph.graph_type,
    join(nodes, "\n"),          // empty string when there are no nodes
    ...sorted(edgeRecords)      // each record is its own length-prefixed field
  ]
  return lowercase_hex(SHA-256(frame(fields)))   // exactly 64 chars; no "sha256:" prefix
```

Self-check against §3.5 before relying on the verifier. Implementations that hash JSON text, emit a `sha256:` prefix, or diverge from the field list / per-edge framing above will not match.

---

## 4. Run metadata canonicalization

### 4.1 Input schema

Run fixtures are JSON objects (`run.json`) with required fields:

| Field | Type | Description |
|---|---|---|
| `run_id` | string | Unique run identifier. |
| `experiment_id` | string | Parent experiment. |
| `graph_id` | string | Associated graph (must match graph fixture). |
| `started_at` | string | ISO-8601 UTC instant; drives signing key selection. |
| `parameters` | object | String keys → string values. |
| `tags` | object | String keys → string values. |

Additional fields in the input file are ignored for digest computation unless listed above.

### 4.2 Canonical bytes

Length-prefixed UTF-8 fields in order:

1. Domain separator: `GRAPHRUN.RUN.v1`
2. `run_id`
3. `experiment_id`
4. `graph_id`
5. `started_at`
6. Sorted `parameters` as lines `key=value`, joined by newline. Sort lines lexicographically.
7. Sorted `tags` as lines `key=value`, joined by newline. Sort lines lexicographically.

**Run digest** = lowercase hex SHA-256 of the framed bytes.

---

## 5. HTTP API

Default bind address: **`127.0.0.1:18082`** (loopback only).

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness probe. Returns **200** when the service process is up. |
| `POST` | `/v1/callbacks` | Accept MLflow run lifecycle callbacks (see §6–§7). |
| `POST` | `/v1/runs/{runId}/sign` | Produce attestation and manifest for a terminal run. |
| `GET` | `/v1/runs/{runId}` | Return current run state (status, digests, callback history metadata). |

### 5.1 Policy-not-ready behavior

If policy recovery has not succeeded (§1.3), all signing and callback endpoints return **503** with a structured error. `/health` may still return **200** if the process is alive but not policy-ready — document this in responses via a `policy_ready: false` field or equivalent structured body.

---

## 6. Callback JSON

### 6.1 Schema source

Callbacks must validate against the JSON Schema extracted from the verified MLflow release:

```
mlflow/server/graphql/schemas/run_callback.schema.json
```

relative to the MLflow extraction root produced by `/app/pkg/ops/fetch-mlflow-release.sh`.

**`/app/docs/bundled/run_callback.schema.json` is not authoritative.** It is a stale, non-normative approximation retained for historical triage only. It deliberately omits contract-valid statuses (including `PENDING`) and uses obsolete field names (for example `timestamp` instead of `occurred_at`). Validating callbacks against that file — or against any classpath copy of it — will reject legitimate initial `PENDING` callbacks and must not be used. The only accepted schema source is the path written to `$MLFLOW_RELEASE_CACHE/schema.path` by `/app/pkg/ops/fetch-mlflow-release.sh` after SHA-256-verified extract.

**Lazy per-request resolution (cold-start):** The signing API must read `$MLFLOW_RELEASE_CACHE/schema.path` **on every callback validation and every sign request**, then open the path written in that marker. Do **not** resolve the marker once in a Spring `@Bean` constructor / factory method and reuse that path for the process lifetime, and do **not** fall back to the bundled approximation when the marker is missing at JVM start. Verifiers commonly clear `/app/.cache/mlflow-release`, start a fresh JVM, then run `fetch-mlflow-release.sh` (or re-fetch) after the API process is already up — a construction-time snapshot either binds the stale bundled schema or fails while an interactive warm session (marker already present before `start-pkg.sh`) still appears to work.

### 6.2 Required fields

| Field | Type | Description |
|---|---|---|
| `event_id` | string | Unique callback event identifier (replay key). |
| `run_id` | string | Target run. |
| `experiment_id` | string | Parent experiment. |
| `graph_digest` | string | Lowercase hex SHA-256 of canonical graph bytes (§3). |
| `policy_version` | string | Must match active recovered policy (`2026.1`). |
| `schema_version` | string | Callback schema version (must match schema `version` or contract in MLflow schema). |
| `status` | string | One of: `PENDING`, `RUNNING`, `FINISHED`, `FAILED`, `KILLED`. |
| `occurred_at` | string | ISO-8601 UTC timestamp of the event. |
| `metrics` | object | Metric name → numeric value map. |

### 6.3 Optional fields

| Field | When required |
|---|---|
| `artifact_digest` | **Required** when `status` is `FINISHED`, `FAILED`, or `KILLED`. Lowercase hex SHA-256. |

### 6.4 Validation failures

Schema validation failures, wrong `policy_version`, or missing required fields → HTTP **400** with structured error category. Never echo raw request bodies or secrets in error responses or logs.

---

## 7. Callback state machine

### 7.1 Allowed transitions

| From | To |
|---|---|
| `PENDING` | `RUNNING` |
| `PENDING` | `KILLED` |
| `RUNNING` | `FINISHED` |
| `RUNNING` | `FAILED` |
| `RUNNING` | `KILLED` |

The **initial** accepted callback for a run may be `PENDING` or `RUNNING` (run creation).

**Terminal states** (`FINISHED`, `FAILED`, `KILLED`) never regress. Any callback attempting to move out of a terminal state → HTTP **409** or **400**.

### 7.2 Run identity binding

For every callback, `run_id`, `experiment_id`, and `graph_digest` must match the registered run expectations derived from `/data/runs` fixtures and prior accepted callbacks. Mismatch → HTTP **400**.

**Synthetic / novel `run_id` values are first-class.** Callback intake MUST accept a schema-valid initial callback (`PENDING` or `RUNNING`) for a `run_id` that has **no** corresponding directory under `/data/runs` and was never pre-registered from fixtures. The first accepted callback for that `run_id` creates the in-memory run record and binds identity (below). Requiring an on-disk fixture file, a pre-seeded `RunStateStore` entry, or any other disk-backed registration before accepting such callbacks is **non-compliant** — verifier suites POST synthetic ids such as `callback-replay-run` and `identity-run` with no matching `/data/runs/<id>/` tree.

**Fixture placeholder digests** — Callback JSON files under `/data/runs/*/callbacks/` may contain a non-normative placeholder `graph_digest` (commonly 64 zero hex digits). That on-disk placeholder is **not** the §3 digest of `graph.json` and is **not** by itself the registered fixture expectation. When driving fixture-backed intake (for example from `/app/pkg/ops/generate-signing-manifest.sh`), compute the §3 framed digest of that run’s `graph.json` and substitute it into each callback **before** POST (also align `run_id` / `experiment_id` with `run.json`). A raw `sha256` over the on-disk `graph.json` bytes (or any other non-§3 hash) is **not** a compliant substitute even when it rewrites the zeros. A correct workflow therefore never relies on leaving the all-zero placeholder unbound/substituted, and never treats “any 64-hex rewrite” as sufficient. Do **not** pre-register expectations solely from `graph.json` and then HTTP **400** unsubstituted placeholder callback files while leaving the driver script posting those placeholders unchanged — fix the driver (or equivalent intake path) so presented digests match §3(`graph.json`).

After a run exists (from a fixture-backed workflow **or** from that first synthetic accept), the first accepted callback for a given `run_id` **binds** that run's `experiment_id` and `graph_digest` **as presented in that accepted callback** (after any fixture substitution above). Any later callback for the same `run_id` that presents a different `experiment_id` or `graph_digest` is an identity mismatch → HTTP **400**, even when the new values would otherwise be schema-valid. Binding applies to runs registered only through the API as well as to fixture-backed runs. Signed `run-attestation.json` / `signing-manifest.json` `graph_digest` fields must be the §3 digest of the run’s `graph.json`, not a leftover placeholder.

### 7.3 Acceptance and replay semantics

**HTTP status table (normative)** — Clients and verifiers observe these statuses on `/v1/callbacks`:

| Outcome | HTTP status | Notes |
|---|---|---|
| First-time accepted callback (including synthetic first `PENDING` / `RUNNING`) | **200** | Not **202**. REST “Accepted” is non-compliant here. |
| Exact replay (same `event_id` + same canonical body digest) | **200** | Same status and same success body shape as the original acceptance. |
| Replay conflict (same `event_id`, different body digest) | **409** | Not **400**. |
| Identity mismatch after bind (`experiment_id` or `graph_digest`) | **400** | Both fields must match the bound values. |
| Schema / transition / terminal-regression rejection | **400** (or **409** for terminal regression) | See §7.2 / transition rules. |

**Success response body** — Every newly accepted callback and every exact replay MUST return HTTP **200** (never **202**) with a JSON object that includes at least:

```json
{"accepted": true}
```

The `accepted` field MUST be the JSON boolean `true` (not the string `"true"`, and not a substitute shape such as `{"status": "accepted"}` or `{"status": "replayed"}`). Implementations MAY also include identifying fields such as `run_id`, `event_id`, and `status` (the accepted callback’s lifecycle status — the run lifecycle string, not a substitute for the boolean `accepted` field). Exact replays MUST return the same HTTP status and the same response body shape as the original acceptance (still including `"accepted": true`). Returning **202** for a first-time accept while using **200** only for exact replays is non-compliant — both paths use **200**.

**Exact replay** — Same `event_id` **and** same canonical callback body digest (§7.4) as a previously accepted callback:

- Idempotent success: HTTP **200** with the success body above (same body as the original acceptance).
- No state change, no duplicate side effects.

**Replay conflict** — Same `event_id` with a **different** canonical callback body digest:

- HTTP **409** Conflict (not **400**).
- Response `error` category should be a conflict class such as `callback_conflict` / `replay_conflict`.
- Prior accepted event is preserved; the conflicting delivery is rejected.

### 7.4 Callback canonical bytes

Length-prefixed UTF-8 framing:

1. Domain separator: `GRAPHRUN.CALLBACK.v1`
2. Each **required** scalar field as `field_name=value`, sorted lexicographically by field name. Include: `event_id`, `run_id`, `experiment_id`, `graph_digest`, `policy_version`, `schema_version`, `status`, `occurred_at`. Include `artifact_digest` when present in the payload.
3. Each metric as `metrics.<name>=<canonical decimal representation>`, sorted lexicographically by full line.

**Callback digest** = lowercase hex SHA-256 of framed bytes.

The **terminal callback** is the last accepted callback whose `status` is `FINISHED`, `FAILED`, or `KILLED`. Signing requires a terminal callback.

---

## 8. MLflow release fetch

Script: `/app/pkg/ops/fetch-mlflow-release.sh`

### 8.1 Configuration

| Variable | Default | Purpose |
|---|---|---|
| `MLFLOW_RELEASE_URL` | `http://127.0.0.1:18081/releases/mlflow-2.16.2.tar.gz` | Full loopback mirror URL for the pinned MLflow source release. The path **must** include the `/releases/` prefix and tarball filename. A host-only value such as `http://127.0.0.1:18081` is incorrect — the mirror serves the archive at `/releases/mlflow-2.16.2.tar.gz`. |
| `MLFLOW_RELEASE_SHA256_FILE` | `/data/mlflow-release/mlflow-2.16.2.sha256` | Expected SHA-256 digest file (`<hex>  <filename>` or hex alone). |
| `MLFLOW_RELEASE_CACHE` | `/app/.cache/mlflow-release` | Local cache root. |

### 8.2 Fetch and verify

1. Download the tarball from `MLFLOW_RELEASE_URL` when not cached, or reuse a cached copy.
2. On **every** use — including cache hits — compute SHA-256 of the **tarball file bytes on disk** and compare to the expected hex from `MLFLOW_RELEASE_SHA256_FILE`. **If the cached tarball fails SHA-256 verification, exit non-zero — do not refetch.** Do not delete, truncate, overwrite, or otherwise “heal” the on-disk archive and retry the download; do not extract. Fail closed on the mutated bytes.
3. **Reject redirects** whose final origin (`scheme://host:port`) differs from the configured `MLFLOW_RELEASE_URL` origin.
4. Extract into a directory under `MLFLOW_RELEASE_CACHE` keyed by the tarball digest (for example `extracted/<hex>/`). Reject archive entries that escape the extraction root (path traversal).
5. Locate `mlflow/server/graphql/schemas/run_callback.schema.json` under the extraction root.
6. Write the absolute schema path to `$MLFLOW_RELEASE_CACHE/schema.path` (one line, trailing newline optional).

**Inter-script `schema.path` handoff (normative):** Step 6 is the documented contract between `/app/pkg/ops/fetch-mlflow-release.sh` and every downstream consumer. `/app/pkg/ops/generate-signing-manifest.sh` and the signing API **must** read `$MLFLOW_RELEASE_CACHE/schema.path` (default cache root `/app/.cache/mlflow-release`) to locate the verified callback schema for hashing and validation. Do not invent a parallel marker name, assume a hardcoded extract path without the marker, or fall back to `/app/docs/bundled/run_callback.schema.json`. A `generate-signing-manifest.sh` rewrite that expects a different handoff file will crash or validate against the wrong schema even when fetch succeeded.

**Cache-hit verification must actually fail on mutation:** re-hash the cached archive contents on every invocation; do not treat “file exists under a name derived from the expected digest”, a warm `schema.path` marker, a prior `.verified-*` / `.verified-<hex>` sidecar, or a prior extract directory as proof the on-disk tarball is still intact. The comparison’s non-zero exit must propagate to the script (with `set -e`, prefer a direct `exit 1` on mismatch). Patterns that hide failure — for example early-exit when `schema.path` already points at a readable file, early-exit when a `.verified-*` marker exists beside the cache archive, `sha256sum … >/dev/null` followed by ignoring status, `if verify_cache; then …; fi` where a mutated cache still takes the success path, or **detecting a digest mismatch and then deleting/refetching the archive so the script exits 0** — do not satisfy this section.

**Worked example (cache-hit re-verification):** Suppose a prior successful fetch left `$MLFLOW_RELEASE_CACHE/mlflow-2.16.2.tar.gz`, a readable `$MLFLOW_RELEASE_CACHE/schema.path`, and optionally a `.verified-<hex>` sidecar. On the next invocation the script must still:

1. Resolve the expected hex from `MLFLOW_RELEASE_SHA256_FILE`.
2. Compute SHA-256 of the **on-disk** tarball bytes (not the sidecar name, not a prior log line).
3. If the digests differ — for example an operator truncated or overwrote the cached archive — print a mismatch diagnostic if desired, then **`exit 1` immediately**. Do not delete the archive, do not re-download, do not rewrite `schema.path`, and do not treat the warm marker as success.
4. Only when the digests match may the script reuse the existing extract / refresh `schema.path` and exit 0.

A compliant one-liner shape (illustrative; any equivalent fail-closed check is fine):

```bash
actual=$(sha256sum "$archive" | awk '{print $1}')
expected=$(awk '{print $1; exit}' "$MLFLOW_RELEASE_SHA256_FILE")
if [ "$actual" != "$expected" ]; then
  echo "digest mismatch: actual=$actual expected=$expected" >&2
  exit 1
fi
```

Logging both digests without the `exit 1` branch — or logging a match then returning success because `schema.path` already exists — does not satisfy §8.2.

No public internet access is required or permitted; the loopback release mirror started by `/app/pkg/ops/start-release-mirror.sh` is the sole source.

---

## 9. Signed attestation payload (Ed25519)

The Ed25519 signature covers the following length-prefixed UTF-8 fields **in order**:

1. Domain separator: `GRAPHRUN.ATTEST.v1`
2. Policy Git commit ID (40 lowercase hex characters from §1.3)
3. Policy document SHA-256 (lowercase hex of raw `config/signing-policy.yaml` bytes after recovery)
4. MLflow tarball SHA-256 (verified digest from §8)
5. Callback schema SHA-256 (lowercase hex of raw `run_callback.schema.json` bytes from verified release)
6. Graph canonical digest (§3)
7. Run metadata digest (§4)
8. Terminal callback digest (§7.4)
9. Signing key ID (selected per §2.3)
10. Attestation schema version (from policy, typically `"1"`)

**Excluded from signed bytes:** wall-clock timestamps, absolute filesystem paths, unsorted map serialization, JSON wrapper objects, and any field not listed above.

Sign with the selected Ed25519 private key (PKCS#8). Encode the signature as **standard base64** (no line breaks) in the output JSON.

---

## 10. Output artifacts

Successful signing writes two files under the output directory. The default directory is `/output/`. When the environment variable `GRAPHRUN_OUTPUT` is set to an absolute path, both `/app/pkg/ops/generate-signing-manifest.sh` and the signing API must write `run-attestation.json` and `signing-manifest.json` under that directory instead of `/output/`. Operators and verifiers may redirect outputs this way; hardcoding only `/output/` fails equivalent-input reruns that set `GRAPHRUN_OUTPUT`.

**Per-invocation override (not startup-only):** Verifiers commonly set a fresh absolute `GRAPHRUN_OUTPUT` on individual `/app/pkg/ops/generate-signing-manifest.sh` process environments while the signing API JVM is already running from an earlier start (often still bound to the default `/output/`). A configuration value captured only at API process start — for example Spring `graphrun.output: ${GRAPHRUN_OUTPUT:/output}` resolved once into a long-lived bean — does **not** observe those later per-script values. Each script invocation must still leave both artifacts under the `GRAPHRUN_OUTPUT` in effect for **that** process (or under `/output/` when unset). Acceptable approaches include reading `GRAPHRUN_OUTPUT` inside `generate-signing-manifest.sh` on every run and writing/copying the artifacts there (for example from the `/v1/runs/{run_id}/sign` response plus the companion manifest), resolving the directory on each sign request rather than from a startup-only snapshot, or an equivalent mechanism that does not require the verifier to restart the API between redirects.

### 10.1 `run-attestation.json` (under the effective output directory)

The on-disk file must be a **flat** JSON object whose **top-level** keys are exactly the fields below (keys sorted lexicographically when writing). Do **not** nest those fields under an `"attestation"` (or similar) wrapper key — even if an HTTP sign response temporarily uses a wrapper, the written `run-attestation.json` must expose the fields at the root. Verifiers read `attestation["graph_digest"]` (and the other keys) directly from the file root.

| Field | Description |
|---|---|
| `attestation_schema_version` | From policy. |
| `callback_schema_sha256` | §9 field 5. |
| `graph_digest` | §3 digest of the run’s `graph.json` (never a fixture placeholder). |
| `mlflow_tarball_sha256` | §9 field 4. |
| `policy_commit_id` | §9 field 2. |
| `policy_digest` | §9 field 3. |
| `run_digest` | §4 digest. |
| `signature` | Base64 Ed25519 signature over §9 framed bytes. |
| `signing_key_id` | §9 field 9. |
| `terminal_callback_digest` | §7.4 digest of terminal callback. |

All digest fields are exactly 64 lowercase hex characters with **no** `sha256:` prefix. **No** `generatedAt`, path fields, or other extraneous keys.

Equivalent inputs must produce **byte-identical** `run-attestation.json` regardless of JSON field order in inputs, edge order in graph fixtures, cache state, temporary paths, or map iteration order. The default output directory is `/output/` when `GRAPHRUN_OUTPUT` is unset; successful visible workflows must leave the two artifacts there for verifier checks that do not inject an override. Validating only under a temporary `GRAPHRUN_OUTPUT` override is insufficient — when the override is unset, `/output/signing-manifest.json` and `/output/run-attestation.json` must still carry a non-empty `policy_commit_id` (40 lowercase hex) from authorized policy recovery.

### 10.2 `signing-manifest.json` (under the effective output directory)

Must validate against `/app/docs/signing-manifest.schema.json` (agent-visible; treat that schema as normative for field names and shapes). Emit a **flat** JSON object — not a nested envelope, not `manifest.json`, and not per-artifact `.sha256` sidecars in place of the schema.

Required top-level fields (exact names):

| Field | Constraint |
|---|---|
| `manifest_schema_version` | string const `"1"` |
| `policy_version` | string |
| `policy_commit_id` | 40 lowercase hex |
| `policy_digest` | 64 lowercase hex |
| `mlflow_tarball_sha256` | 64 lowercase hex |
| `callback_schema_sha256` | 64 lowercase hex |
| `graph_digest` | 64 lowercase hex (bare; no `sha256:` prefix) |
| `run_digest` | 64 lowercase hex |
| `terminal_callback_digest` | 64 lowercase hex |
| `signing_key_id` | string |
| `artifacts` | array of `{ "path": string, "sha256": 64-hex }` |

`additionalProperties` is forbidden by the schema. Validate the on-disk object against `/app/docs/signing-manifest.schema.json` before publishing. **Forbidden** top-level keys include (non-exhaustive) `attestation_sha256`, `run_id`, `signature`, `generatedAt`, and any nested envelope — Ed25519 `signature` belongs only in `run-attestation.json` (§10.1), not in `signing-manifest.json`. The `artifacts` array lists every output and input artifact participating in the signing run. Sort `artifacts` by `path` ascending. Write **atomically** (write to a temporary file in the same directory, `fsync`, then `rename`).

---

## 11. Error handling and logging

### 11.1 Structured API errors

Error responses are JSON objects with at minimum:

- `error` — machine-readable category (for example `policy_ambiguous`, `policy_not_recovered`, `callback_conflict`, `invalid_transition`, `schema_validation_failed`, `identity_mismatch`, `signing_key_unavailable`)
- `message` — human-readable summary without secrets

### 11.2 Logging restrictions

**Never** log:

- Private key bytes or PKCS#8 payloads
- Full Ed25519 signatures (truncated diagnostic prefixes are also forbidden)
- Raw callback request bodies (including seed debug formats such as `received callback body=...`)
- Contents of `/data/keys/*.pk8`

Structured logs may include run IDs, event IDs, digest prefixes (first 8 hex chars at most), HTTP status, and error categories. Remove any pre-existing callback-body echo from `CallbackController` (or equivalent) before shipping.

### 11.3 Network defaults

Service bind address and MLflow release mirror default to loopback. Do not bind to `0.0.0.0` unless explicitly overridden by operator environment (not required for task verification).

---

## 12. CLI pipeline

Documented scripts under `/app/pkg/ops/` form the operator pipeline:

| Script | Purpose |
|---|---|
| `build-offline.sh` | Offline Gradle rebuild of **both** `/app/pkg` and `/app/release-mirror`. Must produce `/app/release-mirror/build/libs/release-mirror.jar` (rebuilding only `/app/pkg` is insufficient). Must honor the Gradle environment variables in §12.1. |
| `start-release-mirror.sh` | Start the loopback MLflow release mirror on port **18081** using that jar. |
| `fetch-mlflow-release.sh` | Fetch, verify, extract, and expose the callback schema (§8). |
| `start-pkg.sh` | Start the Spring Boot service on **127.0.0.1:18082** after policy recovery (`SIGNER_PORT` default **18082**). |
| `generate-signing-manifest.sh` | Drive signing for a run fixture directory and emit `signing-manifest.json` under `/output/` or `GRAPHRUN_OUTPUT` (see §12.2). Default `SIGNER_URL` is `http://127.0.0.1:18082`. Placeholder rewrite must use the §3 framed digest of `graph.json`. |
| `reproduce-signing-failures.sh` | Diagnostic script exercising expected failure modes (policy missing, replay conflict, etc.). |

### 12.1 Offline Gradle environment (`build-offline.sh`)

Repair the **in-tree Java / Gradle / Spring Boot** sources under `/app/pkg` and the ops scripts under `/app/pkg/ops`. Do **not** replace the signing API with a Python (or other) sidecar that depends on packages absent from the verifier image (for example undeclared `PyYAML`) — such rewrites commonly pass an agent’s interactive checks and then return HTTP **503** under a clean verifier start. Keep the documented ports, scripts, and artifact paths.

**`PolicyLoader` constructor (normative):** Instantiations of `com.example.graphrun.signer.PolicyLoader` must use the two-argument constructor:

```java
new PolicyLoader(Path policyPath, Path repoRoot)
```

Typical wiring from `GraphRunProperties`:

```java
new PolicyLoader(properties.policyPath(), properties.repoRoot())
```

`policyPath` is the on-disk YAML path (after recovery: `/app/pkg/config/signing-policy.yaml`). `repoRoot` is the Git working tree root (default `/app/pkg`) used to resolve repository-relative config paths such as `config/signing-policy.yaml.BUILTIN`. A one-argument `new PolicyLoader(policyPath)` call does not compile against the shipped type and will block offline rebuilds.

Verifiers inject a clean Gradle home and an explicit Gradle binary. `/app/pkg/ops/build-offline.sh` MUST honor these variables when set (do not ignore them or hardcode only `./gradlew`):

| Variable | Default | Purpose |
|---|---|---|
| `GRADLE_BIN` | `/opt/gradle/bin/gradle` | Absolute path of the Gradle executable used for offline `clean test assemble`. Prefer `"${GRADLE_BIN}"` over assuming the project wrapper alone. |
| `GRADLE_USER_HOME` | implementation-defined temp home | Gradle user home for the offline build; verifiers supply a clean home seeded from the cache template. |
| `GRADLE_CACHE_TEMPLATE` | `/opt/gradle-cache-template` | Optional seed directory copied into `GRADLE_USER_HOME` when that home has no `caches/` yet. |

A rewrite of `build-offline.sh` that drops `GRADLE_BIN` support will fail clean-home offline rebuilds even when local `./gradlew` appears to work interactively.

### 12.2 `generate-signing-manifest.sh` invocation

Usage:

```bash
/app/pkg/ops/generate-signing-manifest.sh <absolute-run-directory>
```

The sole positional argument is an **absolute filesystem path to a run fixture directory** (for example `/data/runs/visible-run-a` or `/data/runs/visible-run-b`). That directory contains `graph.json`, `run.json`, and `callbacks/`. Do **not** pass a bare `run_id` string, a relative path that depends on an unspecified cwd, or the path of an individual JSON file.

Before signing, the script (or an equivalent driver) must:

1. Ensure the release mirror and signing API are up (or start them via the documented ops scripts).
2. Run `/app/pkg/ops/fetch-mlflow-release.sh` so `$MLFLOW_RELEASE_CACHE/schema.path` exists (§8.2).
3. Read `schema.path`, hash that schema file for `callback_schema_sha256`, and drive fixture callbacks / sign as specified in §7 and §10.

Typical flow:

1. `build-offline.sh` (must leave `release-mirror.jar` in place)
2. `start-release-mirror.sh` (background)
3. `fetch-mlflow-release.sh` (writes `$MLFLOW_RELEASE_CACHE/schema.path`)
4. `start-pkg.sh` (background; triggers policy recovery)
5. Deliver callbacks for runs under `/data/runs`
6. `POST /v1/runs/{runId}/sign` or `generate-signing-manifest.sh /data/runs/visible-run-a`
7. Verify `run-attestation.json` and `signing-manifest.json` under the effective output directory (`GRAPHRUN_OUTPUT` or `/output/`)

---

## 13. Determinism requirements

The following must not affect canonical digests or output artifact bytes:

- JSON key ordering in input files
- Edge ordering in graph fixtures
- Presence of ignored graph fields (`layout`, etc.)
- MLflow cache hit vs miss (after successful digest verification)
- Temporary extraction directory names
- In-memory map iteration order during processing

The following **must** cause rejection without leaking secrets:

- Mismatched `run_id`, `experiment_id`, or `graph_digest`
- Replay conflicts (§7.3)
- Invalid state transitions (§7.1)
- Unauthorized or ambiguous policy recovery (§1.3)
- Disallowed or unavailable signing keys (§2.3)
- Callbacks failing MLflow schema validation (§6)
- Wrong or superseded `policy_version`

---

## 14. Cross-reference index

| Topic | Contract section | Operations manual |
|---|---|---|
| Policy version **2026.1** | §1, §2 | Policy version history |
| Approval roster | §1.2 | §2026.1 approval roster |
| Approval window (UTC inclusive) | §1.2 | §2026.1 approval window |
| Superseded policies | §1.2 | Supersession notice |
| Key rotation | §2.3 | Key rotation notices |
| Incident context | §1 | Incident INF-4412 |
