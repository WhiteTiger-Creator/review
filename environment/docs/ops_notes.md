# Ops notes

Workspace root is `/app`.

Default development build:

```bash
cargo build -p probe
```

Per-arm builds go through `scripts/build_arm.sh`. Aggregate runs use `scripts/run_matrix.sh`, which writes `/app/output/matrix_report.json`. Row and map fields are listed in `contracts/report_schema.md`.

Feature flags `bx` and `by` select the optional native shims under `native/`.

Per-arm probe rows land under `/app/output/` as `arm_b1.json`, `arm_d3.json`, and siblings named `arm_<id>.json`. Probe binaries under `target/` must be real ELF images (magic `ELF`).
