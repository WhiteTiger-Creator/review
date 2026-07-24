#!/bin/bash
set -euo pipefail

# Oracle: build /app/audit — the cosign quorum auditor. The hand-rolled keyed
# MAC, the order-dependent aggregate combine, and the positional roster replay
# (enroll/remove/rotate voiding, threshold, per-release verification) are all
# implemented in Main.java on the JDK standard library alone with no
# javax.crypto and no third-party jar; fully offline.

cd /app
mkdir -p /app/output /app/src /app/classes

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SRC_DIR/Main.java" /app/src/Main.java

javac -d /app/classes /app/src/Main.java

cat > /app/audit <<'WRAP'
#!/bin/bash
exec java -cp /app/classes Main "$@"
WRAP
chmod +x /app/audit

ls -l /app/audit /app/classes/Main.class
