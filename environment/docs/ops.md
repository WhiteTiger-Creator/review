# Soft-TPM lab operations

Rebuild:

```bash
bash /app/environment/tools/mk_all.sh
```

Pinned seat, weave, and seal (preferred multi-stage path):

```bash
/app/bin/lab seat \
  --prep 7 \
  --banks /app/environment/data/banks/sha1.json,/app/environment/data/banks/sha256.json \
  --arms alpha,bravo,charlie

/app/bin/lab weave --arms alpha,bravo,charlie

/app/bin/lab seal \
  --nv /app/environment/data/nv/counter_seed.bin \
  --out-blob /app/output/pol_blob.bin \
  --out-view /app/output/settle_view.json
```

Convenience one-shot (same stages under the hood):

```bash
/app/bin/lab synth \
  --prep 7 \
  --banks /app/environment/data/banks/sha1.json,/app/environment/data/banks/sha256.json \
  --arms alpha,bravo,charlie \
  --nv /app/environment/data/nv/counter_seed.bin \
  --out-blob /app/output/pol_blob.bin \
  --out-view /app/output/settle_view.json
```

Held-out coverage adds `held_x2` to `--arms`. Seat pins `/app/var/seat.lock` with `arms_digest = sha256(arms_csv_bytes)`. Weave refuses a mismatched arm list. Weave writes `/app/var/weave.bin`; seal consumes it.

Recover live NV after damage (prefers `/app/var/gens/<epoch>/seed.bin`, else durable `seed_hex`):

```bash
/app/bin/lab recover
```

Replay settle_view from the generation snapshot without re-weaving:

```bash
/app/bin/lab replay --out-view /app/output/settle_view.json
```

Soft-TPM helpers:

```bash
/app/bin/lab_tpm session
bash /app/environment/tools/softtpm_boot.sh
/app/bin/lab_tpm unseal \
  --blob /app/output/pol_blob.bin \
  --fixture /app/environment/data/profiles/alpha.json \
  --nv-live /app/var/nv_live.bin
```
