#!/usr/bin/env bash
set -euo pipefail

cd /app

sed -i 's/rust-version = "1.85"/rust-version = "1.88"/' Cargo.toml
sed -i 's/crossbeam-channel = "=0.5.14"/crossbeam-channel = "=0.5.15"/' Cargo.toml
sed -i 's/serde = { version = "=1.0.219"/serde = { version = "=1.0.220"/' Cargo.toml
sed -i 's/serde-json-wasm = "=1.0.0"/serde-json-wasm = "=1.0.1"/' Cargo.toml
sed -i 's/time = { version = "=0.3.36"/time = { version = "=0.3.47"/' Cargo.toml

mv .cargo/config.toml /tmp/cargo-reconcile-initial-config.toml
cargo update -p serde --precise 1.0.220
cargo update -p serde-json-wasm --precise 1.0.1
cargo update -p crossbeam-channel --precise 0.5.15
cargo update -p time --precise 0.3.47

mv vendor "/tmp/cargo-reconcile-initial-vendor-$$"
cargo vendor --locked vendor >/tmp/cargo-vendor-config.txt
install -m 0644 /solution/final-config.toml .cargo/config.toml
install -m 0644 /solution/deny.toml deny.toml

cargo metadata --locked --offline --format-version 1 >/tmp/cargo-reconcile-metadata.json
cargo test --workspace --all-targets --locked --offline
cargo audit --json >/tmp/cargo-reconcile-audit.json
cargo deny --all-features check advisories bans licenses sources

rustsec_commit="$(git ls-remote https://github.com/RustSec/advisory-db HEAD | awk 'NR == 1 {print $1}')"
test "${#rustsec_commit}" -eq 40

lock_hash="$(sha256sum Cargo.lock | awk '{print $1}')"
run_id="${lock_hash:0:20}"
resolved_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
rust_version="$(rustc --version | head -n 1)"
cargo_version="$(cargo --version | head -n 1)"
audit_version="$(cargo audit --version | head -n 1)"
deny_version="$(cargo deny --version | head -n 1)"

mkdir -p release
ledger="release/dependency-ledger.sqlite"
if [ -e "$ledger" ]; then
    mv "$ledger" "/tmp/dependency-ledger.$$.sqlite"
fi
sqlite3 "$ledger" < docs/release-ledger.sql
sqlite3 "$ledger" <<SQL
BEGIN IMMEDIATE;
INSERT INTO release_run VALUES(
  '$run_id', '$resolved_at', '$rust_version', '$cargo_version',
  '$audit_version', '$deny_version', '$lock_hash', '$rustsec_commit', 1, 1
);
INSERT INTO dependency_change VALUES(
  '$run_id', 'crossbeam-channel', '0.5.14', '0.5.15',
  'RUSTSEC-2025-0024', 1, '1.60'
);
INSERT INTO dependency_change VALUES(
  '$run_id', 'serde-json-wasm', '1.0.0', '1.0.1',
  'RUSTSEC-2024-0012', 0, ''
);
INSERT INTO dependency_change VALUES(
  '$run_id', 'time', '0.3.36', '0.3.47',
  'RUSTSEC-2026-0009', 0, '1.88.0'
);
INSERT INTO policy_check VALUES(
  '$run_id', 'cargo-metadata', 'cargo metadata --locked --offline --format-version 1', 'pass'
);
INSERT INTO policy_check VALUES(
  '$run_id', 'cargo-test', 'cargo test --workspace --all-targets --locked --offline', 'pass'
);
INSERT INTO policy_check VALUES(
  '$run_id', 'cargo-audit', 'cargo audit --json', 'pass'
);
INSERT INTO policy_check VALUES(
  '$run_id', 'cargo-deny', 'cargo deny --all-features check advisories bans licenses sources', 'pass'
);
COMMIT;
SQL

sed \
  -e "s|@@RESOLVED_AT@@|$resolved_at|g" \
  -e "s|@@RUSTSEC_COMMIT@@|$rustsec_commit|g" \
  -e "s|@@LOCK_HASH@@|$lock_hash|g" \
  -e "s|@@RUST_VERSION@@|$rust_version|g" \
  -e "s|@@CARGO_VERSION@@|$cargo_version|g" \
  -e "s|@@AUDIT_VERSION@@|$audit_version|g" \
  -e "s|@@DENY_VERSION@@|$deny_version|g" \
  /solution/reconciliation.template.md > release/reconciliation.md
