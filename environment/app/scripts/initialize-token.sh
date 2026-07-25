#!/usr/bin/env bash
# Deterministically initialize SoftHSM tokens and export public keys for the sample environment.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOKEN_STORE="${TOKEN_STORE:-$ROOT/token-store}"
CONF="${SOFTHSM2_CONF:-$ROOT/config/softhsm2.conf}"
MODULE="${PKCS11_MODULE:-/usr/lib/softhsm/libsofthsm2.so}"
if [[ ! -f "$MODULE" ]]; then
  MODULE="/usr/lib/x86_64-linux-gnu/softhsm/libsofthsm2.so"
fi
PIN_FILE="$ROOT/config/token-user.pin"
SO_PIN_FILE="$ROOT/config/token-so.pin"
PUBLIC_DIR="$ROOT/config/public"

mkdir -p "$TOKEN_STORE" "$PUBLIC_DIR" "$(dirname "$CONF")"
echo "directories.tokendir = $TOKEN_STORE" > "$CONF"
echo "objectstore.backend = file" >> "$CONF"
echo "log.level = ERROR" >> "$CONF"

export SOFTHSM2_CONF="$CONF"

USER_PIN="$(tr -d '\n' < "$PIN_FILE")"
SO_PIN="$(tr -d '\n' < "$SO_PIN_FILE")"

rm -rf "${TOKEN_STORE:?}/"*

# SoftHSM may rewrite serials to slot-derived values; we capture them after init.
softhsm2-util --init-token --free --label "release-token" --serial "1001" --so-pin "$SO_PIN" --pin "$USER_PIN"
softhsm2-util --init-token --free --label "legacy-token" --serial "2001" --so-pin "$SO_PIN" --pin "$USER_PIN"

token_serial() {
  local label="$1"
  pkcs11-tool --module "$MODULE" -T 2>/dev/null | awk -v want="$label" '
    /token label/ { gsub(/^[[:space:]]+|[[:space:]]+$/, "", $0); sub(/^token label[[:space:]]*:[[:space:]]*/, "", $0); label=$0 }
    /serial num/ && label == want {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", $0);
      sub(/^serial num[[:space:]]*:[[:space:]]*/, "", $0);
      print $0;
      exit
    }
  '
}

RELEASE_SERIAL="$(token_serial release-token)"
LEGACY_SERIAL="$(token_serial legacy-token)"
if [[ -z "$RELEASE_SERIAL" || -z "$LEGACY_SERIAL" ]]; then
  echo "failed to discover SoftHSM serial numbers" >&2
  pkcs11-tool --module "$MODULE" -T >&2 || true
  exit 1
fi

# Rewrite current-format URIs with the live serials while preserving documented attribute shape.
python3 - "$ROOT" "$RELEASE_SERIAL" "$LEGACY_SERIAL" <<'PY'
import sys
from pathlib import Path
root = Path(sys.argv[1])
release_serial = sys.argv[2]
legacy_serial = sys.argv[3]
text = (root / "config" / "current.toml").read_text()
text = text.replace("serial=1001", f"serial={release_serial}")
(root / "config" / "current.toml").write_text(text)
(root / "config" / "token-serials.env").write_text(
    f"RELEASE_SERIAL={release_serial}\nLEGACY_SERIAL={legacy_serial}\n"
)
print(f"release-token serial={release_serial}")
print(f"legacy-token serial={legacy_serial}")
PY

gen_pair() {
  local id="$1"
  local label="$2"
  local out_pem="$3"
  local token_label="$4"
  pkcs11-tool --module "$MODULE" \
    --token-label "$token_label" \
    --login --pin "$USER_PIN" \
    --keypairgen --key-type rsa:2048 \
    --label "$label" --id "$id" \
    --usage-sign >/dev/null

  pkcs11-tool --module "$MODULE" \
    --token-label "$token_label" \
    --login --pin "$USER_PIN" \
    --read-object --type pubkey --id "$id" \
    --output-file "${out_pem}.der" >/dev/null

  openssl pkey -pubin -inform DER -in "${out_pem}.der" -outform PEM -out "$out_pem" 2>/dev/null \
    || openssl rsa -pubin -inform DER -in "${out_pem}.der" -outform PEM -out "$out_pem"
  rm -f "${out_pem}.der"
}

gen_pair 01 release-signing "$PUBLIC_DIR/release-primary.pem" release-token
gen_pair 02 release-signing "$PUBLIC_DIR/release-secondary.pem" release-token
gen_pair 01 legacy-signing "$PUBLIC_DIR/legacy.pem" legacy-token

echo "SoftHSM sample tokens initialized under $TOKEN_STORE"
