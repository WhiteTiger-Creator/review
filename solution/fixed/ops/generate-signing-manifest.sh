#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <run-directory>" >&2
  exit 2
fi

RUN_DIR="$(cd "$1" && pwd)"
SIGNER_URL="${SIGNER_URL:-http://127.0.0.1:18082}"
OUTPUT_DIR="${GRAPHRUN_OUTPUT:-/output}"

/app/pkg/ops/start-release-mirror.sh
/app/pkg/ops/fetch-mlflow-release.sh
/app/pkg/ops/start-pkg.sh

python3 - <<'PY' "${RUN_DIR}" "${SIGNER_URL}" "${OUTPUT_DIR}"
import json, hashlib, pathlib, subprocess, sys, tempfile, urllib.request

run_dir = pathlib.Path(sys.argv[1])
signer = sys.argv[2].rstrip("/")
output = pathlib.Path(sys.argv[3])
output.mkdir(parents=True, exist_ok=True)

graph = json.loads((run_dir / "graph.json").read_text())
run = json.loads((run_dir / "run.json").read_text())

# Compute graph digest via local Java helper if available; otherwise approximate using service after register.
# Prefer invoking the running service's canonicalize by signing only after callbacks with digest from a small python port.
# We use a minimal compatible digest by calling a local python framing that matches the contract.

def nfc(s: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFC", s)

def frame(fields: list[str]) -> bytes:
    out = bytearray()
    for f in fields:
        b = f.encode("utf-8")
        out += len(b).to_bytes(4, "big") + b
    return bytes(out)

def normalize_weight(raw: str) -> str:
    from decimal import Decimal
    v = raw.strip()
    if v.startswith("."):
        v = "0" + v
    d = Decimal(v).normalize()
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"

def graph_digest(g: dict) -> str:
    undirected = g.get("graph_type") == "undirected"
    nodes = sorted({nfc(n["id"]) for n in g.get("nodes", [])})
    edges = []
    for e in g.get("edges", []):
        src, tgt = nfc(e["source"]), nfc(e["target"])
        if undirected and src.encode() > tgt.encode():
            src, tgt = tgt, src
        attrs = e.get("attributes")
        if attrs is None:
            attrs_json = ""
        else:
            attrs_json = json.dumps(attrs, sort_keys=True, separators=(",", ":"))
        edges.append("\0".join([src, tgt, e.get("kind", ""), normalize_weight(str(e.get("weight", "0"))), attrs_json]))
    edges = sorted(set(edges))
    fields = ["GRAPHRUN.GRAPH.v1", g.get("graph_id", ""), g.get("graph_type", ""), "\n".join(nodes), *edges]
    return hashlib.sha256(frame(fields)).hexdigest()

digest = graph_digest(graph)
run_id = run["run_id"]

cb_dir = run_dir / "callbacks"
for cb_path in sorted(cb_dir.glob("*.json")):
    cb = json.loads(cb_path.read_text())
    cb["graph_digest"] = digest
    cb["run_id"] = run_id
    cb["experiment_id"] = run["experiment_id"]
    data = json.dumps(cb).encode()
    req = urllib.request.Request(f"{signer}/v1/callbacks", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        if resp.status >= 400:
            raise SystemExit(f"callback failed: {resp.status}")

mlflow_sha = open("/data/mlflow-release/mlflow-2.16.2.sha256").read().split()[0].lower()
payload = {
    "run_id": run_id,
    "graph": graph,
    "run": run,
    "mlflow_tarball_sha256": mlflow_sha,
}
req = urllib.request.Request(
    f"{signer}/v1/runs/{run_id}/sign",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req) as resp:
    body = resp.read()
(output / "run-attestation.json").write_bytes(body if body.endswith(b"\n") else body + b"\n")
print(f"Wrote {output}/run-attestation.json and {output}/signing-manifest.json")
PY
