# Ops notes

Workspace root is `/app`.

Default development build:

```bash
cargo build -p probe
```

Per-arm builds go through `scripts/build_arm.sh`. Aggregate runs use `scripts/run_matrix.sh`, which writes `/app/output/matrix_report.json` and one `/app/output/arm_<id>.json` row per documented arm. Row and map fields are listed in `contracts/report_schema.md`.

Feature flags `bx` and `by` select the optional native shims under `native/`. The `by` flag pulls in a companion crate that enables the wide cfg on the digest helper crate, so companion spans differ across arms that share the `bx` backend.

Per-arm probe rows land under `/app/output/` as `arm_a0.json`, `arm_b1.json`, `arm_c2.json`, and `arm_d3.json`. Probe binaries under `target/` must be real ELF images (magic bytes `\\x7fELF`). Verifier hygiene may touch `/tmp` and `/var/tmp` while cleaning stale session sockets.

Static-link arms read `NEXUS_LINK_MODE` / `NEXUS_STATIC` from the matrix contract and from `.cargo/config.toml`. LTO arms set `NEXUS_LTO` per the contract.
