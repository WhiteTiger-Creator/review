# Mesh Posture Output (normative)

The `meshgate reconcile` command replays signed streams from `--data-root` against mesh policy in `--policy` and writes posture JSON to `--output`.

Stream validation rules live in `/app/spec/mesh_stream_protocol.md`. Signature payloads format telemetry and tune floats with exactly 4 decimal places.

## Top-level schema

| Field | Type | Description |
|-------|------|-------------|
| recoverable | boolean | `true` only if every site directory is recoverable. |
| gateways | array | Sites sorted by `gateway_id` ascending. |
| drift_events | array | Findings sorted by `gateway_id` ascending, then `seq` ascending. |

All list fields (`gateways`, `drift_events`, and `metrics` inside a unit) must serialize as JSON arrays (`[]`), never `null`.

When `--data-root` is missing or not a directory, emit `recoverable: false`, `gateways: []`, and `drift_events: []`.

## `gateways[]`

| Field | Type | Description |
|-------|------|-------------|
| gateway_id | string | Site directory name. |
| recoverable | boolean | Whether this site is recoverable. |
| processed_records | integer | Count of all non-empty input lines scanned across all segment files, including lines that produced drift events. |
| units | array | Active unit states. Empty when this gateway's `recoverable` is `false`. Sorted by `unit_id` ascending. |

### `units[]`

| Field | Type | Description |
|-------|------|-------------|
| unit_id | string | Unit identifier. |
| active | boolean | `true` if the unit is discovered and not retired at stream end. |
| metrics | array | Summaries sorted by `metric` ascending. |

### `metrics[]`

| Field | Type | Description |
|-------|------|-------------|
| metric | string | Metric name. |
| min | float | Minimum adjusted value. |
| max | float | Maximum adjusted value. |
| average | float | Arithmetic mean of adjusted values. |
| count | integer | Number of applied readings. |

## `drift_events[]`

| Field | Type | Description |
|-------|------|-------------|
| gateway_id | string | Site where a stream finding occurred, or `""` for policy findings. |
| seq | integer | Source record sequence for stream findings, or `0` for policy findings. |
| unit_id | string | Unit involved in a stream finding or a `site_forbidden` finding; otherwise `""`. |
| reason | string | Finding category. |
| detail | string | Exact detail string. |

### Drift event ordering
Sort `drift_events` by `(gateway_id, seq)` ascending. Empty `gateway_id` (`""`) sorts before any non-empty gateway name. When multiple events share the same `(gateway_id, seq)`, preserve the order in which they were emitted (stable ordering).

## Stream drift reasons

| reason | Condition | Detail format |
|--------|-----------|---------------|
| `duplicate_seq` | seq already processed | `duplicate sequence number: <seq>` |
| `invalid_seq` | seq does not match expected | `invalid sequence: expected <exp>, got <seq>` |
| `invalid_timestamp` | invalid or retrogressive timestamp | `retrogressive or invalid timestamp: <ts>` |
| `unknown_op_or_metric` | unknown op, missing metric, or missing unit_id | `unknown op '<op>' or missing metric` |
| `bad_signature` | signature mismatch or malformed JSON line | `signature hash mismatch` |
| `orphan_batch` | commit/abort without batch | `batch boundary op without open transaction` |
| `nested_batch` | begin while batch open | `nested transaction begin not allowed` |
| `tune_missing_unit` | TUNE before BOOT | `cannot tune undiscovered unit: <unit>` |
| `orphan_unit` | TELEMETRY/PING before BOOT | `orphan unit event: <unit>` |
| `stale_unit_op` | event after SHUTDOWN | `event on retired unit: <unit>` |

## Policy evaluation

Policy rules come from `--policy` JSON (`bound_nodes`, `home_sites`, `sync_metrics`).

### Gating
Policy evaluation runs **only when global `recoverable` is `true`**. If any gateway is unrecoverable, skip all policy checks — do not emit `binding_breach`, `site_forbidden`, or `sync_skew` events.

When policy evaluation runs, consider only units listed in `gateways[].units` on recoverable gateways. Retired units (`active: false`) are present in output but are **not** active for policy checks.

### Evaluation order
Emit policy drift events in this fixed order:

1. **`bound_nodes`** — for each pair in policy file array order, then for each gateway in `gateway_id` ascending order.
2. **`home_sites`** — for each unit in `unit_id` ascending order, then for each gateway in `gateway_id` ascending order.
3. **`sync_metrics`** — for each metric name in lexicographic ascending order.

All policy drift events use `gateway_id: ""`, `seq: 0`.

### Policy drift reasons

| reason | Condition | Detail format |
|--------|-----------|---------------|
| `binding_breach` | On a gateway, at least one member of a bound pair is active but both are not active on that same gateway | `binding broken: <left> and <right> not co-present` |
| `site_forbidden` | An active unit appears on a gateway outside its home-site allow list | `unit <unit> seen on foreign site <site>` |
| `sync_skew` | A sync metric's per-gateway reference averages differ by more than `0.05` across at least two gateways | `sync metric skew: <metric> exceeds tolerance` |

### `binding_breach` semantics

Bound-node policy enforces **co-location per gateway**, not fleet-wide presence.

For each bound pair `(left, right)` and each gateway `G`:

1. Determine whether `left` is **active** on `G` (discovered, not retired, listed in `G`'s output units with `active: true`).
2. Determine whether `right` is **active** on `G` under the same rules.
3. If **at least one** side is active on `G` but **both are not** active on `G`, emit **one** `binding_breach` drift event.

**Event shape:** Policy-wide — always `gateway_id: ""`, `seq: 0`, `unit_id: ""`. Do **not** populate `gateway_id` with the violating site even though evaluation is per-gateway.

**Multiplicity:** The same pair may produce **multiple** events — one per violating gateway. Do **not** deduplicate. Identical `detail` strings are expected when several gateways breach the same pair.

**No breach cases:**
- Neither side is active on `G` → no event for that pair on `G`.
- Both sides are active on `G` → no event for that pair on `G`.
- One side active on `G`, the other active only on a different gateway → **still a breach on `G`**.

#### Worked example: `binding_breach`
Policy: `bound_nodes: [{"left": "alpha", "right": "beta"}]`

After replay:

| gateway | alpha active? | beta active? | breach? |
|---------|---------------|--------------|---------|
| `gw_A` | yes | no (retired) | **yes** — alpha present without active beta |
| `gw_B` | yes | absent | **yes** — alpha present without active beta |
| `gw_C` | no | no | no |

Emit **two** drift events (evaluation order: `gw_A` before `gw_B`):

```json
[
  {
    "gateway_id": "",
    "seq": 0,
    "unit_id": "",
    "reason": "binding_breach",
    "detail": "binding broken: alpha and beta not co-present"
  },
  {
    "gateway_id": "",
    "seq": 0,
    "unit_id": "",
    "reason": "binding_breach",
    "detail": "binding broken: alpha and beta not co-present"
  }
]
```

Both events are identical except they occupy separate positions in the emission order (stable under final sorting because `(gateway_id, seq)` ties).

### `site_forbidden` semantics

For each unit listed in `home_sites` and each gateway where that unit is **active**, the gateway must appear in the unit's allow list. Each violation emits one policy event with `unit_id` set to the violating unit.

A unit may be authorized on multiple gateways; appearing on any gateway **not** in its allow list is a violation.

### `sync_skew` semantics

**Per-gateway reference average:** For each gateway and each sync metric name, collect the `average` from every output unit on that gateway that reports the metric. When multiple units on the same gateway report the same sync metric, use the value from the unit with the greatest `unit_id` in lexicographic order (last writer wins).

**Comparison:** A sync metric is evaluated only when at least two gateways each have a reference average for that metric. Compare the maximum and minimum reference averages across gateways; emit `sync_skew` when `(max − min) > 0.05` (strictly greater than `0.05`).

#### Worked example: `sync_skew`
Policy: `sync_metrics: ["temp"]`

| gateway | reference average for `temp` |
|---------|-------------------------------|
| `gw1` | `20.0` |
| `gw2` | `20.10` |

Difference `0.10 > 0.05` → emit one `sync_skew` event with detail `sync metric skew: temp exceeds tolerance`.

If only one gateway reports `temp`, or the difference is exactly `0.05`, emit nothing.

## CLI

```bash
meshgate reconcile \
  [--data-root/--data = /app/data] \
  [--policy = /app/spec/mesh_policy.json] \
  [--output = /app/output/posture.json]
```

`--data-root` and `--data` are aliases.
