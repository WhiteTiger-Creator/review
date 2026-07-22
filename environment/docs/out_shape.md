# settle_view and pol_blob rules

Bank tables under `/app/environment/data/banks/` expose `entries` with `name` and `sum` (64-char hex).

`/app/output/settle_view.json` fields:

- `arms`: objects `{name,sum}` in `--arms` request order
- `byte_len`: length of `/app/output/pol_blob.bin` (≤ `max_blob_bytes`)
- `view_digest`: sha256 hex of pol_blob bytes (64 lowercase; all-zero invalid)
- `nv_token`: hex of the epoch-bound NV token embedded in the blob
- `bank_tag`: selected bank id (`sha256` under the published size ceiling)
- `epoch`: pinned `--prep` value; also stored inside the blob
- `arms_digest`: sha256 hex of the exact `--arms` CSV bytes from the seat
- `sync_label`: must be `settled`
- `phase_digest`: sha256 of `/app/var/phase.jsonl` after bind is recorded
- `lineage_hex`: sha256 of `bank_tag|nv_token|view_digest|epoch|arms_digest`

Phase journal lines are JSON objects `{"stage":"...","epoch":N}` in order `fold`, `pack`, `bind` for the pinned epoch.

NV token formula (Soft-TPM and seal must agree):

`nv_token = hx_nv_token_from_seed(seed) XOR (epoch * HX_EPOCH_MIX)`

`HX_EPOCH_MIX` is the constant published in `/app/environment/lib/core/codec.h`. Raw seed bytes alone are not a valid token. Blob magic is `HXP2` and carries `epoch` ahead of `nv_token` on the wire.

Under the size ceiling the viable bank is `sha256`. Denser `sha1` coverage fails Soft-TPM tag checks.

Generation snapshots land at `/app/var/gens/<epoch>/` with `blob.bin`, `view.json`, `seed.bin`, and `phase.jsonl`. Durable state `/app/var/durable.json` retains `epoch`, `view_digest`, `bank_tag`, `nv_token`, `arms_digest`, and `seed_hex`.
