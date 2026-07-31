#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <run-directory>" >&2
  exit 2
fi

RUN_DIR="$(cd "$1" && pwd)"
SIGNER_PORT="${SIGNER_PORT:-8080}"
SIGNER_URL="${SIGNER_URL:-http://127.0.0.1:${SIGNER_PORT}}"
OUTPUT_DIR="${GRAPHRUN_OUTPUT:-/output}"
MANIFEST_CLI_JAR="${MANIFEST_CLI_JAR:-/app/pkg/cli/build/libs/cli.jar}"

/app/pkg/ops/start-release-mirror.sh
/app/pkg/ops/fetch-mlflow-release.sh
/app/pkg/ops/start-pkg.sh

RUN_META="$(python3 - <<'PY' "${RUN_DIR}/run.json"
import json, sys
from pathlib import Path
run = json.loads(Path(sys.argv[1]).read_text())
print(run["run_id"])
print(run["experiment_id"])
PY
)"
RUN_ID="$(printf '%s\n' "${RUN_META}" | sed -n '1p')"
EXPERIMENT_ID="$(printf '%s\n' "${RUN_META}" | sed -n '2p')"

GRAPH_JSON="$(python3 - <<'PY' "${RUN_DIR}/graph.json"
import json, sys
from pathlib import Path
print(json.dumps(json.loads(Path(sys.argv[1]).read_text())))
PY
)"

CALLBACK_DIR="${RUN_DIR}/callbacks"
if [[ ! -d "${CALLBACK_DIR}" ]]; then
  echo "callbacks directory missing: ${CALLBACK_DIR}" >&2
  exit 1
fi

shopt -s nullglob
callbacks=("${CALLBACK_DIR}"/*.json)
IFS=$'\n' callbacks_sorted=($(printf '%s\n' "${callbacks[@]}" | sort))
unset IFS

GRAPH_DIGEST="$(python3 - <<'PY' "${RUN_DIR}/graph.json"
import hashlib, json, sys, unicodedata
from decimal import Decimal
from pathlib import Path

def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)

def frame(fields: list[str]) -> bytes:
    out = bytearray()
    for f in fields:
        b = f.encode("utf-8")
        out += len(b).to_bytes(4, "big") + b
    return bytes(out)

def normalize_weight(raw: str) -> str:
    v = (raw or "").strip()
    if not v:
        return "1"
    if v.startswith("."):
        v = "0" + v
    try:
        d = Decimal(v).normalize()
        s = format(d, "f")
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        return s or "1"
    except Exception:
        return v

g = json.loads(Path(sys.argv[1]).read_text())
undirected = g.get("graph_type") == "undirected"
nodes = sorted({nfc(n["id"]) for n in g.get("nodes", []) if n.get("id")})
edges = []
for e in g.get("edges", []):
    src, tgt = nfc(e.get("source", "")), nfc(e.get("target", ""))
    if undirected and src > tgt:
        src, tgt = tgt, src
    attrs = e.get("attrs")
    if attrs is None:
        attrs_json = ""
    else:
        attrs_json = json.dumps(attrs, sort_keys=True, separators=(",", ":"))
    weight = normalize_weight(str(e["weight"]) if "weight" in e and e["weight"] is not None else "1")
    edges.append("\0".join([src, tgt, e.get("kind", ""), weight, attrs_json]))
edges = sorted(set(edges))
fields = [
    "GRAPHRUN.GRAPH.v1",
    g.get("graph_id", ""),
    g.get("graph_type", ""),
    "\n".join(nodes),
    "\n".join(edges),
]
print(hashlib.sha256(frame(fields)).hexdigest())
PY
)"

for cb in "${callbacks_sorted[@]}"; do
  echo "POST callback $(basename "${cb}")"
  POST_BODY="$(python3 - <<'PY' "${cb}" "${GRAPH_DIGEST}" "${RUN_ID}" "${EXPERIMENT_ID}"
import json, sys
from pathlib import Path
cb = json.loads(Path(sys.argv[1]).read_text())
digest = sys.argv[2]
run_id = sys.argv[3]
experiment_id = sys.argv[4]
placeholder = cb.get("graph_digest", "")
if set(placeholder) <= {"0"}:
    cb["graph_digest"] = digest
cb["run_id"] = run_id
cb["experiment_id"] = experiment_id
print(json.dumps(cb, separators=(",", ":")))
PY
)"
  curl -fsS -H 'Content-Type: application/json' \
    -d "${POST_BODY}" \
    "${SIGNER_URL}/v1/callbacks" >/dev/null
done

MLFLOW_SHA="$(awk '{print $1}' "${MLFLOW_RELEASE_SHA256_FILE:-/data/mlflow-release/mlflow-2.16.2.sha256}")"
SCHEMA_PATH="$(cat "${MLFLOW_RELEASE_CACHE:-/app/.cache/mlflow-release}/schema.path")"
SCHEMA_SHA="$(sha256sum "${SCHEMA_PATH}" | awk '{print $1}')"

SIGN_REQUEST="$(python3 - <<'PY' "${RUN_DIR}/run.json" "${GRAPH_JSON}" "${MLFLOW_SHA}" "${SCHEMA_SHA}"
import json, sys
run = json.loads(open(sys.argv[1]).read())
graph = json.loads(sys.argv[2])
payload = {
    "run_id": run["run_id"],
    "graph": graph,
    "mlflow_tarball_sha256": sys.argv[3],
    "callback_schema_sha256": sys.argv[4],
}
print(json.dumps(payload))
PY
)"

echo "POST sign for run ${RUN_ID}"
curl -fsS -H 'Content-Type: application/json' \
  -d "${SIGN_REQUEST}" \
  "${SIGNER_URL}/v1/runs/${RUN_ID}/sign" \
  -o "${OUTPUT_DIR}/.sign-response.json"

mkdir -p "${OUTPUT_DIR}"
if [[ -f "${OUTPUT_DIR}/${RUN_ID}/attestation.json" ]]; then
  cp "${OUTPUT_DIR}/${RUN_ID}/attestation.json" "${OUTPUT_DIR}/run-attestation.json"
else
  python3 - <<'PY' "${OUTPUT_DIR}/.sign-response.json" "${OUTPUT_DIR}/run-attestation.json"
import json, sys
from pathlib import Path
resp = json.loads(Path(sys.argv[1]).read_text())
att = resp.get("attestation", resp)
Path(sys.argv[2]).write_text(json.dumps(att, indent=2, sort_keys=True) + "\n")
PY
fi

java -jar "${MANIFEST_CLI_JAR}" "${OUTPUT_DIR}" \
  run-attestation.json=pending \
  signing-manifest.json=pending

if [[ -f "${OUTPUT_DIR}/manifest.json" ]]; then
  mv "${OUTPUT_DIR}/manifest.json" "${OUTPUT_DIR}/signing-manifest.json"
fi

echo "Wrote ${OUTPUT_DIR}/run-attestation.json and ${OUTPUT_DIR}/signing-manifest.json"
