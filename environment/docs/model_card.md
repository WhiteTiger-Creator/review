# Model card — ETA residual evaluation service

Family: offline quantized residual ETA model with registry-bound promotion of inference settings.

Weights: /app/environment/assets/weights.json

Exported graph: /app/environment/assets/model.onnxsub

Scale manifest: /app/environment/assets/manifest.json (declared_scale anchors bound M1 only)

Evaluation quality: metamorphic T1 agreement, D1 dynamic range, and M1 envelope under the active registry generation. Promotion and ledger rules are defined in run_schema.md.
