# Dependency release reconciliation

Resolved at: @@RESOLVED_AT@@

RustSec HEAD: `@@RUSTSEC_COMMIT@@`

Cargo.lock SHA-256: `@@LOCK_HASH@@`

The release moves three quarantined crates onto the first current policy-safe versions.

| Package | From | To | Reason |
| --- | --- | --- | --- |
| `crossbeam-channel` | `0.5.14` | `0.5.15` | The old release is yanked and is covered by RUSTSEC-2025-0024. |
| `serde-json-wasm` | `1.0.0` | `1.0.1` | RUSTSEC-2024-0012 is fixed at the selected 1.x boundary. |
| `time` | `0.3.36` | `0.3.47` | RUSTSEC-2026-0009 is fixed here; this release raises the workspace MSRV to Rust 1.88. |

Tool versions used:

* `@@RUST_VERSION@@`
* `@@CARGO_VERSION@@`
* `@@AUDIT_VERSION@@`
* `@@DENY_VERSION@@`

Checks completed:

```text
cargo metadata --locked --offline --format-version 1
cargo test --workspace --all-targets --locked --offline
cargo audit --json
cargo deny --all-features check advisories bans licenses sources
```

The Rust source baseline was not changed during this dependency release.
