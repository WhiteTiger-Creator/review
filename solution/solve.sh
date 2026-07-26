#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_DIR=/app/broker/src/main/java/com/acme/wallet/sdjwt

# Replace the stub with the JDK-only implementation: canonical JSON, base64url and digest helpers,
# JWK handling with RFC 7638 thumbprints, SD-JWT disclosure resolution, the minimal release search
# and the key binding JWT.
mkdir -p "$PKG_DIR"
rm -f "$PKG_DIR"/*.java
cp "$SCRIPT_DIR"/src/*.java "$PKG_DIR"/

cd /app/broker
mvn -B -q clean package

test -f /app/broker/target/sd-jwt-broker.jar

# Prove the packaged broker runs against the batch shipped with the environment.
java -jar /app/broker/target/sd-jwt-broker.jar \
    --config /app/broker/wallet.properties \
    --credentials /app/credentials \
    --policy /app/broker/policy.json \
    --out /app/out

test -f /app/out/report.json
echo "built /app/broker/target/sd-jwt-broker.jar"
