# Dependency release policy

The workspace is at `/app`. This policy defines the dependency release handoff. The operation uses Cargo's own resolver and the installed RustSec policy tools. It does not add an application, helper command, or generated source.

## Scope

Only these paths may change:

* `/app/Cargo.toml`
* `/app/Cargo.lock`
* `/app/.cargo/config.toml`
* `/app/vendor/`
* `/app/deny.toml`
* `/app/release/dependency-ledger.sqlite`
* `/app/release/reconciliation.md`

Files below `/app/crates`, `/app/docs`, `/app/sql`, and `/app/tooling` are the release baseline. Their bytes must stay unchanged. Do not add scripts, binaries, build files, source files, patches, or local replacement crates.

## Quarantined dependencies

The release begins with three exact workspace pins. Each one has a live policy problem:

| Package | Starting version | Current reason |
| --- | --- | --- |
| `serde-json-wasm` | `1.0.0` | `RUSTSEC-2024-0012`; the fixed 1.x boundary starts at `1.0.1` |
| `crossbeam-channel` | `0.5.14` | yanked and covered by `RUSTSEC-2025-0024`; the fixed boundary starts at `0.5.15` |
| `time` | `0.3.36` | `RUSTSEC-2026-0009`; the fixed boundary starts at `0.3.47` |

Query the current crates.io index and RustSec database before selecting releases. For each package, choose the lowest non-yanked version at or above the listed fixed boundary that the current advisory database considers safe. Keep the same semver line shown by the starting version. If current data adds a later fixed boundary, that later boundary wins.

The selected `time` release sets the workspace MSRV. The `0.3.47` line requires Rust 1.88, so `[workspace.package].rust-version` must be at least `1.88` and must not exceed the Rust 1.89 toolchain in this image. Do not raise the MSRV beyond what the selected release needs.

Write all three final requirements as exact `=VERSION` entries in `[workspace.dependencies]`. There must be one locked version of each quarantined crate. Do not use a git dependency, `[patch]`, path override, advisory ignore, yank ignore, or source-code workaround.

The selected `time` release uses the split `serde_core` packaging introduced at Serde 1.0.220. Move the existing exact workspace `serde` pin from `1.0.219` to exactly `1.0.220` so Cargo resolves one matching derive/core set. Preserve the other direct workspace pins. This supporting resolver move does not add a fourth quarantine ledger row.

## Reproducible Cargo state

Regenerate `/app/Cargo.lock` with Cargo's resolver. Preserve lockfile format 4 and registry checksums. Refresh `/app/vendor` from that final locked graph. The final `/app/.cargo/config.toml` has exactly this source policy:

```toml
[source.crates-io]
replace-with = "vendored-sources"

[source.vendored-sources]
directory = "vendor"

[net]
git-fetch-with-cli = true
```

With external network disabled, all of these must succeed from `/app`:

```text
cargo metadata --locked --offline --format-version 1
cargo test --workspace --all-targets --locked --offline
```

The vendor directory may contain only packages selected by the final lock graph and Cargo's target-aware vendor operation. Each vendored package directory is named for the package alone, with no version suffix. Keep Cargo's checksum files intact.

## cargo-deny policy

Create `/app/deny.toml` for cargo-deny 0.19.4. The `[graph]` section contains `all-features = true`.

The `[advisories]` section contains exactly these two keys:

```toml
[advisories]
ignore = []
git-fetch-with-cli = true
```

Do not add `db-urls` or `db-path`. Omitting those keys selects cargo-deny's default RustSec database.

Use these settings in the other sections:

* license confidence is `0.8`; workspace crates are checked; the allowed expressions are `Apache-2.0`, `Apache-2.0 WITH LLVM-exception`, `BSD-3-Clause`, `ISC`, `MIT`, `Unicode-3.0`, and `Zlib`;
* multiple versions warn, wildcard requirements deny, and both `skip = []` and `skip-tree = []` are present so no crate is skipped;
* the quarantined starting versions are denied with nonempty package-specific reasons. Each item in `bans.deny` uses cargo-deny's compact `crate = "name@=version"` form. The three `crate` values are `serde-json-wasm@=1.0.0`, `crossbeam-channel@=0.5.14`, and `time@=0.3.36`;
* unknown registries and unknown git sources deny. The crates.io index is the only allowed registry, recorded as `allow-registry = ["https://github.com/rust-lang/crates.io-index"]`, and `allow-git = []` records that no git source is allowed.

The live command below must pass with no vulnerability, yank, ban, license, or source error:

```text
cargo deny --all-features check advisories bans licenses sources
```

`cargo audit --json` must also exit successfully against the current default RustSec database. Do not suppress a warning or vulnerability to make either command pass.

## Release ledger

Create `/app/release/dependency-ledger.sqlite` from `/app/docs/release-ledger.sql`. It contains one current release run. Use the lowercase SHA-256 of the final `Cargo.lock` as `cargo_lock_sha256`. Set `run_id` to exactly the first 20 lowercase hexadecimal characters of that same hash. `resolved_at` is the reconciliation time in UTC whole-second form, `YYYY-MM-DDTHH:MM:SSZ`.

Record the first line from each installed version command in the corresponding column:

* `rustc --version`
* `cargo --version`
* `cargo audit --version`
* `cargo deny --version`

`rustsec_commit` is the 40-character lowercase HEAD fetched from the live `https://github.com/RustSec/advisory-db` repository during this operation. Set `offline_replay` and `source_unchanged` to 1.

Add one `dependency_change` row per quarantined package. Use the table's starting version, the selected lockfile version, its listed RustSec ID, and the selected index row's `rust_version`. Store an empty string when the index row omits `rust_version`. Only the `crossbeam-channel` row has `yanked_before = 1`.

Add these four `policy_check` rows with status `pass` and the exact command text shown:

| tool | command |
| --- | --- |
| `cargo-metadata` | `cargo metadata --locked --offline --format-version 1` |
| `cargo-test` | `cargo test --workspace --all-targets --locked --offline` |
| `cargo-audit` | `cargo audit --json` |
| `cargo-deny` | `cargo deny --all-features check advisories bans licenses sources` |

Replacing a prior reconciliation means replacing the old run and its child rows. Do not leave more than one run.

## Handoff note

Write `/app/release/reconciliation.md` in plain technical prose with ASCII punctuation. Include the UTC reconciliation time, RustSec commit, full lockfile hash, tool versions, a three-row before-and-after table with the policy reason for each change, the four checked commands, and one sentence containing the exact terms "source baseline" and "unchanged" that states the source baseline stayed unchanged. Values in the note must match SQLite and the lockfile. Do not paste provider responses, terminal transcripts, or generic release advice.
