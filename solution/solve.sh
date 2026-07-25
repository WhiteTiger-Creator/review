#!/usr/bin/env bash
set -euo pipefail

export PATH="/usr/local/cargo/bin:/app/bin:${PATH:-}"
export SOFTHSM2_CONF="${SOFTHSM2_CONF:-/app/config/softhsm2.conf}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FIXED="${SCRIPT_DIR}/fixed"

if [[ ! -d "$FIXED" ]]; then
  echo "missing fixed sources at $FIXED" >&2
  exit 1
fi

mkdir -p /app/src
cp -a "${FIXED}/." /app/src/
# Keep environment mirror in sync for cargo workspace path.
mkdir -p /app/environment/app
ln -sfn /app/src /app/environment/app/src
ln -sfn /app/Cargo.toml /app/environment/app/Cargo.toml 2>/dev/null || true
ln -sfn /app/Cargo.lock /app/environment/app/Cargo.lock 2>/dev/null || true

if [[ -f /app/Cargo.toml ]]; then
  APP_ROOT=/app
elif [[ -f /app/environment/app/Cargo.toml ]]; then
  APP_ROOT=/app/environment/app
else
  echo "cannot locate Cargo.toml" >&2
  exit 1
fi

mkdir -p "$APP_ROOT/.cargo"
if [[ -f /app/cargo-vendor-config.toml ]]; then
  cp /app/cargo-vendor-config.toml "$APP_ROOT/.cargo/config.toml"
elif [[ -f /app/environment/cargo-vendor-config.toml ]]; then
  cp /app/environment/cargo-vendor-config.toml "$APP_ROOT/.cargo/config.toml"
fi

# Vendor must resolve relative to APP_ROOT (.cargo says ../vendor for /app/environment/app,
# or vendor for /app depending on config). Prefer /app layout with vendor symlink.
if [[ "$APP_ROOT" == "/app" ]]; then
  cat > /app/.cargo/config.toml <<'EOF'
[source.crates-io]
replace-with = "vendored-sources"

[source.vendored-sources]
directory = "vendor"
EOF
  ln -sfn /app/environment/vendor /app/vendor
fi

cd "$APP_ROOT"
touch src/main.rs
cargo build --release --offline --locked

BIN="${APP_ROOT}/target/release/signingd"
if [[ ! -f "$BIN" ]]; then
  BIN="/app/environment/app/target/release/signingd"
fi
mkdir -p /app/bin
install -m 0755 "$BIN" /app/bin/signingd

mkdir -p /app/state /output/signed/jobs /var/log/signing
rm -f /app/state/worker-bootstrap.json || true
/app/bin/signingd run --config /app/config/current.toml || true
/app/bin/signingd inspect --config /app/config/current.toml >/dev/null || true

echo "oracle repair complete"
