# Mesh Edge Stream Protocol (normative)

## Site layout
Each mesh site (gateway directory) stores signed JSONL segments named `seg_NNN.jsonl`. Process segments in lexicographic order; together they form one chronological stream per site.

Gateway directories under `--data-root` are processed in lexicographic order by directory name.

## Record schema
Each JSONL line is an object with:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| seq | integer | yes | Strictly positive, starting at 1 and increasing by 1 for each valid record. |
| ts | string | yes | RFC3339 UTC timestamp. |
| unit_id | string | yes | Reporting unit identifier. |
| op | string | yes | One of `BOOT`, `PING`, `TELEMETRY`, `TUNE`, `BATCH_BEGIN`, `BATCH_COMMIT`, `BATCH_ABORT`, `SHUTDOWN`. |
| metric | string | conditional | Required when `op` is `TELEMETRY`. |
| val | float | conditional | Required when `op` is `TELEMETRY`. Raw telemetry value. |
| offset | float | conditional | Required when `op` is `TUNE`. Offset applied to future telemetry. |
| sig | string | yes | 64-character lowercase hex SHA-256 of the canonical payload. |

### Signature payload
1. Build `gateway_id|seq|ts|unit_id|op|metric|val|offset` where:
   - `gateway_id` is the site directory name.
   - `metric` is the metric string when present, otherwise empty.
   - `val` is formatted with exactly 4 decimal places for `TELEMETRY`, otherwise empty.
   - `offset` is formatted with exactly 4 decimal places for `TUNE`, otherwise empty.
2. SHA-256 the UTF-8 payload and encode as 64-character lowercase hex.

## Validation priority
When a record fails multiple checks, emit only the first applicable reason:

1. `duplicate_seq`
2. `invalid_seq`
3. `invalid_timestamp`
4. `unknown_op_or_metric`
5. `bad_signature`
6. `orphan_batch`
7. `nested_batch`
8. `tune_missing_unit`

### Recoverability

**Gateway recoverability:** A gateway is unrecoverable when any processed record emits `invalid_seq`, `duplicate_seq`, or `bad_signature`. All other drift reasons discard the offending record but leave the gateway recoverable.

**Global recoverability:** Top-level `recoverable` is `true` only when every gateway directory is recoverable.

**Effects of unrecoverability:**
- For an unrecoverable gateway, `gateways[].units` must be `[]` (unit state and metric aggregates are omitted).
- For an unrecoverable gateway, `gateways[].processed_records` still counts every non-empty input line scanned.
- When global `recoverable` is `false`, **policy evaluation is skipped entirely** (no `binding_breach`, `site_forbidden`, or `sync_skew` events are emitted). Stream-level drift events for recoverable gateways are still reported.

### Sequence advancement after violations
- After `invalid_seq` or `duplicate_seq`, the expected sequence number does **not** advance; the next record must still match the previous expectation.
- After any other drift reason (including `bad_signature`), the expected sequence number advances by 1.
- Malformed JSON lines emit `bad_signature` with the current expected sequence, mark the gateway unrecoverable, and do **not** advance the expected sequence.

### Timestamp monotonicity
Among valid records, timestamps must be non-decreasing (`ts` of record *n* ≥ `ts` of record *n−1*). Equal timestamps are allowed. RFC3339 parse failures are `invalid_timestamp`.

## Unit lifecycle

### Discovery and activity
1. A unit becomes **discovered** after a valid `BOOT`.
2. `TELEMETRY`, `PING`, or `TUNE` before `BOOT` is discarded (`orphan_unit` or `tune_missing_unit` per priority).
3. After `SHUTDOWN`, the unit is **retired**; later `TELEMETRY`, `PING`, or `TUNE` yields `stale_unit_op` and is ignored.
4. A second `BOOT` on an already discovered unit reactivates it (`retired` becomes `false`).
5. Output `units[]` includes only discovered units, sorted by `unit_id` ascending. `active` is `true` when the unit is discovered and not retired at stream end.

### Batch transactions
- `BATCH_BEGIN` opens a batch on the current gateway stream.
- While a batch is open, `TELEMETRY` and `TUNE` are **staged** and do not affect public unit state or metric aggregates.
- `BATCH_COMMIT` applies all staged ops in chronological order (the order they were staged), then closes the batch.
- `BATCH_ABORT` discards all staged ops and closes the batch without applying them.
- An open batch at stream end (including end of the last segment file) is treated as an implicit `BATCH_ABORT`.
- Batches may span multiple segment files on the same gateway.
- If a record inside an open batch fails validation, emit the drift event, **abort the batch immediately** (discard staged ops), and resume normal processing. A later `BATCH_COMMIT` or `BATCH_ABORT` without a fresh `BATCH_BEGIN` is `orphan_batch`.
- `BOOT`, `PING`, `SHUTDOWN`, and batch boundary ops themselves are never staged; they execute immediately even when a batch is open.
- During `BATCH_COMMIT`, skip staged ops for units that are retired or undiscovered at commit time.

#### Worked example: batch staging and commit
Gateway `gw_tx`, unit `dev1` boots with default offset `0.0`:

| seq | op | effect |
|-----|-----|--------|
| 2 | `BATCH_BEGIN` | open batch |
| 3 | `TELEMETRY temp=10.0` | staged (not applied) |
| 4 | `BATCH_ABORT` | discard staged ops |
| 5 | `BATCH_BEGIN` | open batch |
| 6 | `TELEMETRY temp=15.0` | staged |
| 7 | `TUNE offset=1.0` | staged |
| 8 | `TELEMETRY temp=17.0` | staged |
| 9 | `BATCH_COMMIT` | apply staged ops in order |

Commit application uses the offset **as it stands at the moment each staged op is applied**:
1. `TELEMETRY 15.0` → adjusted `15.0 + 0.0 = 15.0`
2. `TUNE 1.0` → active offset becomes `1.0`
3. `TELEMETRY 17.0` → adjusted `17.0 + 1.0 = 18.0`

Final metric `temp`: `min=15.0`, `max=18.0`, `count=2`, `average=16.5`.

### Calibration offsets (`TUNE`)

**Replacement semantics:** Each applied `TUNE` **replaces** the unit's active calibration offset; offsets do **not** accumulate. The default offset before any `TUNE` is `0.0`.

**Adjusted telemetry:** `adjusted_val = raw_val + active_offset`, using the active offset at the moment the telemetry is applied (outside a batch) or at the moment the staged telemetry is applied during `BATCH_COMMIT`.

**Immediate vs staged application:**
- Outside an open batch, a valid `TUNE` replaces the active offset immediately.
- Inside an open batch, `TUNE` is staged and replaces the active offset only when that staged op is applied during `BATCH_COMMIT` (in chronological order relative to other staged ops).

#### Worked example: successive calibration
Unit `u1` on gateway `gw1`:

| seq | op | active offset after | notes |
|-----|-----|---------------------|-------|
| 1 | `BOOT` | `0.0` | discovered |
| 2 | `TUNE offset=2.0` | `2.0` | replaces default |
| 3 | `TELEMETRY val=10.0` | `2.0` | adjusted reading `12.0` |
| 4 | `TUNE offset=-1.0` | `-1.0` | replaces `2.0` (does not become `1.0`) |
| 5 | `TELEMETRY val=10.0` | `-1.0` | adjusted reading `9.0` |

Metric aggregate uses adjusted values `12.0` and `9.0`: `min=9.0`, `max=12.0`, `count=2`, `average=10.5`.

#### Worked example: calibration inside a batch
Unit `u1`, offset starts at `0.0`, batch opens:

| staged order | op | offset during application | adjusted value |
|--------------|-----|---------------------------|----------------|
| 1 | `TELEMETRY val=20.0` | `0.0` | `20.0` |
| 2 | `TUNE offset=5.0` | — | offset becomes `5.0` |
| 3 | `TELEMETRY val=20.0` | `5.0` | `25.0` |

After commit: `min=20.0`, `max=25.0`, `count=2`, `average=22.5`. A subsequent immediate `TELEMETRY val=20.0` yields `25.0`.

### Telemetry aggregation

Per discovered unit on each gateway, accumulate **applied** (non-staged) `TELEMETRY` readings using **adjusted** values, tracked independently per metric name:

| Field | Rule |
|-------|------|
| `min` | Minimum adjusted value seen |
| `max` | Maximum adjusted value seen |
| `count` | Number of applied readings |
| `average` | Arithmetic mean: running `sum / count` over adjusted values |

**Scope:** Aggregates are per `(gateway, unit_id, metric)` — readings from different gateways are never merged into the same aggregate.

**Floating-point:** Compute aggregates from the raw numeric values produced by calibration; serialize them as JSON numbers. Do not apply additional rounding beyond normal IEEE-754 arithmetic.

**Output ordering:** Emit `metrics[]` sorted by `metric` ascending.

**Aborted or unstaged readings:** Telemetry discarded by batch abort, implicit abort at stream end, or validation failure never contributes to aggregates.
