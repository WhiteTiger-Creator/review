# Ops notes

Workspace root is `/app`.

Default development build:

```bash
cargo build -p probe
```

Per-arm builds go through `scripts/build_arm.sh`. Aggregate runs use `scripts/run_matrix.sh`, which writes `/app/output/matrix_report.json`. Row and map fields are listed in `contracts/report_schema.md`.

Feature flags `bx` and `by` select the optional native shims under `native/`.
