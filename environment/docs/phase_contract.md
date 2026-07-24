# depctrl operator notes

Build from `/app/environment` (offline; no module proxy):

```bash
cd /app/environment && GOPROXY=off go build -mod=readonly -o /app/bin/depctrl ./cmd/depctrl
```

`depctrl collect` loads `/app/environment/data/events/{m_a,m_b,m_h}.jsonl` into `/app/output/run_traces/`. `depctrl reconcile --all-mirrors` seals `/app/output/journal/lock.wal`, consults `/app/output/cache/`, and writes `/app/output/constraint_report.json`. `depctrl emit` seals and folds using already-collected raw lines. `depctrl reconcile` without `--all-mirrors` only writes a partial staging gate. `depctrl status` prints `steady` and is not proof the terminal report is sealed. The manual CLI chain of `depctrl collect` followed by `depctrl reconcile` (without flags) and finally `depctrl emit` must successfully seal a terminal report. A double reconcile on identical inputs must be fully idempotent, yielding the exact same output digests and bounds.

After a successful full reconcile, `/app/output/traces/last_run.json` is a JSON object with integer `row_n`, integer `frame_n`, and boolean `cache_hit`. `row_n` equals the length of the sealed report rows array, and `frame_n` is at least `row_n`.

Sealed frames carry `pkg`, `dep`, `lo`, `hi`, `pre_tok`, `lift`, `act_tok`, `seq`, `arm_tag`, `epoch`, and `crc`. Within one arm tag, only the highest `seq` for a `(pkg, dep)` pair survives sealing. On WAL replay, torn lines or frames whose `crc` does not match the normalized payload are dropped without poisoning the sealed fold. Frame CRC construction lives in the `SealCRC` helper under the journal package. Arm tag `a` treats an empty `pre_tok` as `allow`. Arm tag `b` strips a `-pre.` suffix from `lo`/`hi` when `pre_tok` is not `allow`. Arm tag `h` may carry `peer_hi` on the raw JSONL; ceilings are recovered from that raw file, not from sealed frames.

Cache keys under `/app/output/cache/` must stay coherent when seed bytes, activation map bytes, sealed-frame fingerprint, or live peer fingerprint change. A hit must refuse the blob when the stored peer fingerprint no longer matches the live peer caps. Optional seed edges appear in the folded graph only while their activation key remains true in `/app/environment/data/act_map.json` and the matching `act_tok` was observed on a failing line; warm cache must not resurrect an edge after activation clears.

`/app/output/constraint_report.json` is `{ "rows": [ ... ] }`. Each row has `pkg`, `dep`, `lo`, `hi`, `pre_tok`, `lift`, `row_digest` per `/app/environment/schemas/row_out.schema.json`. Output files must be overwritten on subsequent runs. Folding intersects candidate bounds across arms with semver compare (numeric major.minor.patch first; a release sorts above the same tuple that still carries `-pre.`). When `lift` is true, the resolved `hi` bound is capped by the `peer_hi` value found in the raw events; raising `peer_hi` above the intersection loosens the ceiling. Empty `pre_tok` means emitted bounds must not retain `-pre.`. `row_digest` is the first 16 hex characters of SHA-256 over `{pkg}|{dep}|{lo}|{hi}|{pre_tok}|{lift}` with lift as `1` or `0` (same recipe as the module comment above `/app/environment/y4f/digest.go`).

Primary seeds include required edge `core-a` and optional edge `side-b` (activation key `k_x`).

