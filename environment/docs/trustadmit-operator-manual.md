# trustadmit operator manual

Graded binary: `/app/bin/trustadmit`.

## Verbs

### seal-corpus

```
trustadmit seal-corpus --pool POOL_PATH --binding BINDING_PATH
```

Digests the certificate corpus, advances `/app/state/seal_epoch.json`, writes the binding JSON, and drops `/app/state/.trustadmit_ready`.

Default binding path when omitted by operators: `/app/state/trust_bind.json`.

### bind-issuers

```
trustadmit bind-issuers --binding BINDING_PATH
```

Writes sealed issuer adjacency to `/app/state/issuer_adjacency.json` for the binding.

### attest-chain

```
trustadmit attest-chain --binding BINDING_PATH --roots ROOTS_PATH --target TARGET_ID --time TIMESTAMP --output OUTPUT_PATH
```

Reloads only through the binding. Verifies seal epoch, ready latch, and adjacency witness. Never accepts a direct `--pool` path. On success writes a leaf-to-root id JSON array; on trust failure writes a refusal envelope and exits non-zero.

## State surfaces

| Path | Role |
|------|------|
| `/app/state/trust_bind.json` | Default trust binding |
| `/app/state/seal_epoch.json` | Monotonic seal-epoch ledger |
| `/app/state/.trustadmit_ready` | Seal ready latch |
| `/app/state/issuer_adjacency.json` | Issuer adjacency witness |
