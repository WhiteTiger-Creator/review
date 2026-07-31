#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cleanup() {
  # Tear down oracle smoke services so the verifier can restart cleanly.
  # Remove PID files and escalate to SIGKILL — a lingering/zombied PID makes
  # start-*.sh report "already running" while /health is dead (oracle REWARD=0).
  for pidfile in \
    /tmp/graphrun-signer/graph-run-signer.pid \
    /tmp/graphrun-mirror/release-mirror.pid
  do
    if [[ -f "${pidfile}" ]]; then
      pid="$(cat "${pidfile}" 2>/dev/null || true)"
      if [[ -n "${pid}" ]]; then
        kill "${pid}" 2>/dev/null || true
        for _ in $(seq 1 50); do
          kill -0 "${pid}" 2>/dev/null || break
          sleep 0.1
        done
        kill -9 "${pid}" 2>/dev/null || true
      fi
      rm -f "${pidfile}"
    fi
  done
}
trap cleanup EXIT

require_path() {
  if [[ ! -e "$1" ]]; then
    echo "missing required path: $1" >&2
    exit 1
  fi
}

require_path /app/pkg
require_path "${ROOT_DIR}/pkg-recovery.patch"

# Restore authoritative policy from Git history using the operations-manual rules.
python3 - <<'PY'
import pathlib, subprocess, re
from datetime import datetime, timezone

repo = pathlib.Path("/app/pkg")
window_start = datetime(2026, 1, 5, tzinfo=timezone.utc)
window_end = datetime(2026, 3, 1, 23, 59, 59, tzinfo=timezone.utc)
approvers = {"alice@example.com", "bob@example.com"}

def git(*args):
    return subprocess.check_output(["git", *args], cwd=repo, text=True, stderr=subprocess.STDOUT)

commits = set()
for line in git("log", "--all", "--format=%H", "--", "config/signing-policy.yaml").splitlines():
    if line.strip():
        commits.add(line.strip())
for line in git("reflog", "--all", "--format=%H").splitlines():
    if line.strip():
        commits.add(line.strip())
try:
    for line in git("fsck", "--unreachable", "--no-reflogs").splitlines():
        if line.startswith("unreachable commit "):
            commits.add(line.split()[-1])
except subprocess.CalledProcessError:
    pass

authorized = []
for cid in commits:
    try:
        yaml = git("show", f"{cid}:config/signing-policy.yaml")
    except subprocess.CalledProcessError:
        continue
    if 'policy_version: "2026.1"' not in yaml and "policy_version: '2026.1'" not in yaml and "policy_version: 2026.1" not in yaml:
        continue
    meta = git("log", "-1", "--format=%cI%n%B", cid)
    date_s, _, body = meta.partition("\n")
    ts = datetime.fromisoformat(date_s.replace("Z", "+00:00"))
    if ts < window_start or ts > window_end:
        continue
    m = re.search(r"(?im)^Approved-By:\s*(\S+)", body)
    if not m or m.group(1).lower() not in approvers:
        continue
    authorized.append((cid, yaml))

if len(authorized) != 1:
    raise SystemExit(f"expected exactly one authorized policy, found {len(authorized)}")

cid, yaml = authorized[0]
policy = repo / "config" / "signing-policy.yaml"
policy.write_text(yaml)
print(f"restored policy from {cid}")
PY

# Patch paths are pkg/<module>/... relative to /app.
cd /app
if git -C /app/pkg apply --check -p2 "${ROOT_DIR}/pkg-recovery.patch" 2>/dev/null; then
  git -C /app/pkg apply -p2 "${ROOT_DIR}/pkg-recovery.patch"
elif command -v patch >/dev/null 2>&1 && patch -p1 --dry-run < "${ROOT_DIR}/pkg-recovery.patch" >/dev/null 2>&1; then
  patch -p1 < "${ROOT_DIR}/pkg-recovery.patch"
else
  # Fallback when patch(1) is unavailable: overlay corrected sources from solution/fixed.
  python3 - <<'PY' "${ROOT_DIR}/fixed"
import pathlib, sys
src_root = pathlib.Path(sys.argv[1])
repo = pathlib.Path("/app/pkg")
ops = repo / "ops"
for src in src_root.rglob("*"):
    if not src.is_file():
        continue
    rel = src.relative_to(src_root)
    dst = ops.joinpath(*rel.parts[1:]) if rel.parts[0] == "ops" else repo.joinpath(*rel.parts)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())
print("applied fixed sources")
PY
fi

chmod +x /app/pkg/ops/*.sh

# Harbor mounts /output at runtime; ensure it exists before oracle smoke cleanup/writes.
# Dockerfile intentionally does not pre-create /output (OracleFix.md / Daytona boot).
mkdir -p /output

rm -rf \
  /app/pkg/build \
  /app/pkg/*/build \
  /app/release-mirror/build \
  /app/.cache/mlflow-release \
  /output/*

export GRADLE_USER_HOME=/tmp/graphrun-oracle-gradle
export GRADLE_CACHE_TEMPLATE=/opt/gradle-cache-template
mkdir -p /tmp/graphrun-oracle-gradle
if [[ ! -d /tmp/graphrun-oracle-gradle/caches && -d /opt/gradle-cache-template ]]; then
  cp -a /opt/gradle-cache-template/. /tmp/graphrun-oracle-gradle/
fi

/app/pkg/ops/build-offline.sh
/app/pkg/ops/start-release-mirror.sh
/app/pkg/ops/fetch-mlflow-release.sh
/app/pkg/ops/start-pkg.sh
/app/pkg/ops/generate-signing-manifest.sh /data/runs/visible-run-a

require_path /output/run-attestation.json
require_path /output/signing-manifest.json

python3 - <<'PY'
import json, pathlib
att = json.loads(pathlib.Path("/output/run-attestation.json").read_text())
man = json.loads(pathlib.Path("/output/signing-manifest.json").read_text())
assert "signature" in att and len(att["signature"]) > 20
assert man["manifest_schema_version"] == "1"
assert att["policy_commit_id"] == man["policy_commit_id"]
print("oracle smoke checks passed")
PY
