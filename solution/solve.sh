# Oracle solve — task identity x509-path-reconstructor token 59cebf22
#!/bin/bash
# Oracle solve — X.509 trust admission attestation
set -euo pipefail

PATH="/app/bin:/opt/verifier-venv/bin:/usr/local/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

patch --batch -p2 -d /app/src < "${ROOT_DIR}/solution.patch"

cd /app
cargo build --release --locked
mkdir -p /app/bin
cp -f /app/target/release/trustadmit /app/bin/trustadmit

test -x /app/bin/trustadmit \
  || { echo "ERROR: trustadmit binary not found at /app/bin/trustadmit"; exit 1; }

echo "X.509 trust admission attestation oracle completed."
