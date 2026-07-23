#!/usr/bin/env bash
# Build and run one matrix arm. Args: arm_id
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ARM_ID="${1:?arm id}"
MATRIX="$ROOT/contracts/matrix_arms.json"
OUT="${NEXUS_OUT:-/app/output}"
mkdir -p "$OUT"

python3 - <<'PY' "$MATRIX" "$ARM_ID" "$OUT" "$ROOT"
import json, os, subprocess, sys
matrix_path, arm_id, out, root = sys.argv[1:5]
data = json.load(open(matrix_path))
arm = next(a for a in data["arms"] if a["id"] == arm_id)
feats = arm.get("features") or []
feat_args = []
for f in feats:
    feat_args.extend(["--features", f])
profile = arm.get("profile", "dev")
mode = arm["mode"]
env = os.environ.copy()
env["NEXUS_ARM"] = arm_id
env["NEXUS_MODE"] = mode
env["NEXUS_OUT"] = out
for k, v in (arm.get("env") or {}).items():
    env[k] = str(v)
# Isolate target dirs per arm so feature/cfg graphs do not collide.
env["CARGO_TARGET_DIR"] = os.path.join(root, "target", f"arm_{arm_id}")
cmd = ["cargo", "build", "-p", "probe", "--locked"]
if profile == "release":
    cmd.append("--release")
elif profile == "release-lto":
    cmd.extend(["--profile", "release-lto"])
cmd.extend(feat_args)
build = subprocess.run(cmd, cwd=root, env=env)
build_ok = build.returncode == 0
probe_ok = False
digest = None
tag_p = tag_q = ""
tag_agree = False
row_path = os.path.join(out, f"arm_{arm_id}.json")
if build_ok:
    bin_name = "probe"
    if profile == "dev":
        bin_path = os.path.join(env["CARGO_TARGET_DIR"], "debug", bin_name)
    elif profile == "release-lto":
        bin_path = os.path.join(env["CARGO_TARGET_DIR"], "release-lto", bin_name)
    else:
        bin_path = os.path.join(env["CARGO_TARGET_DIR"], "release", bin_name)
    run = subprocess.run([bin_path], env=env)
    probe_ok = run.returncode == 0
    if os.path.isfile(row_path):
        row = json.load(open(row_path))
        digest = row.get("digest")
        tag_p = row.get("tag_p", "")
        tag_q = row.get("tag_q", "")
        tag_agree = bool(row.get("tag_agree"))
summary = {
    "arm_id": arm_id,
    "mode": mode,
    "build_ok": build_ok,
    "probe_ok": probe_ok,
    "digest": digest,
    "tag_p": tag_p,
    "tag_q": tag_q,
    "tag_agree": tag_agree,
    "features": feats,
}
open(os.path.join(out, f"summary_{arm_id}.json"), "w").write(json.dumps(summary))
sys.exit(0 if build_ok else 1)
PY
