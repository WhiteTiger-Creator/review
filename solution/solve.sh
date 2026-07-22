#!/usr/bin/env bash
set -euo pipefail

bash /usr/local/bin/entrypoint.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export ROOT_DIR
cd /app

echo "Applying oracle patches..."
bash "${ROOT_DIR}/apply_java_patches.sh"

cp "${ROOT_DIR}/patches_test/ConfigLoaderTest.java" src/test/java/dev/terminus/trivia/ConfigLoaderTest.java

rm -rf /output/* /app/.state/* 2>/dev/null || true
mkdir -p /output /app/.state

make verify

echo "Oracle solution completed successfully."
