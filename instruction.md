The MLflow model registry in `/app` needs complete architecture metadata for its pinned
Hugging Face transformer checkpoints. Implement the missing transformer-aware logic in:

```text
/app/migrations/V003_backfill_hf_model_metadata.lua
```

For each eligible checkpoint, resolve its immutable Hugging Face revision and interpret
the model configuration to identify the language backbone. Populate its architecture,
residual width, layer and attention layout, feed-forward width, parameter counts,
per-token KV-cache footprint, and architecture fingerprint. Model versions resolving to
the same architecture must share the same architecture record.

The checkpoint set spans encoder, decoder, encoder-decoder, grouped-query,
multi-query, mixture-of-experts, and vision-language transformer configurations. Account
for family-specific configuration names and transformer features such as explicit or
derived head dimensions, gated feed-forward networks, dense and sparse experts,
LayerNorm and RMSNorm, learned and rotary positions, tied embeddings, projection biases,
and checkpoint precision. Values must describe the resolved language-model architecture,
not merely copy fields from one configuration family.

`/app/spec/BACKFILL_CONTRACT.md` is the normative definition of checkpoint eligibility,
revision resolution, configuration precedence, architecture columns, counting
conventions, fingerprint serialization, and repeat execution. `/app/spec/worked/`
contains one complete accounting example and two additional checkpoint inputs.

The migration runs inside a restricted Lua environment with only the supplied `db`,
`http`, `json`, and `crypto` interfaces. Preserve models outside the specified checkpoint
scope and preserve version lineage. Applying the completed migration again to the same
registry must leave its state unchanged.

Validate the result with:

```sh
mvn -q -f /app/pom.xml verify
```
