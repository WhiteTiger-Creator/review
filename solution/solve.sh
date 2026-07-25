#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_DIR=/app/unsealer/src/main/java/com/acme/inbox/jwe

# Replace the stub with the JDK-only implementation: JWK loading and P-256 conversion, the three
# JWE serializations, ECDH-1PU key agreement with the hand-rolled Concat KDF, AES key unwrap and
# AES-GCM decryption, the sender registry fetch, and the canonical report plus transcript digest.
mkdir -p "$PKG_DIR"
rm -f "$PKG_DIR"/*.java
cp "$SCRIPT_DIR"/src/*.java "$PKG_DIR"/

cd /app/unsealer
mvn -B -q clean package

test -f /app/unsealer/target/jwe-unsealer.jar
echo "built /app/unsealer/target/jwe-unsealer.jar"
