#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${DEST:-/data}"
RUNS_DIR="${DEST}/runs"
KEYS_DIR="${DEST}/keys"
MLFLOW_DIR="${DEST}/mlflow-release"
CACHE_SAMPLE_DIR="${DEST}/cache-samples"
SCHEMA_SRC="${SCHEMA_SRC:-${SCRIPT_DIR}/data/run_callback.schema.strict.json}"

mkdir -p "${RUNS_DIR}" "${KEYS_DIR}" "${MLFLOW_DIR}" "${CACHE_SAMPLE_DIR}"

generate_ed25519_key() {
  local name="$1"
  openssl genpkey -algorithm Ed25519 -outform DER -out "${KEYS_DIR}/${name}.pk8" 2>/dev/null
  openssl pkey -inform DER -in "${KEYS_DIR}/${name}.pk8" -pubout -outform DER \
    | tail -c 32 >"${KEYS_DIR}/${name}.pub"
}

for key in signer-2025 signer-2026 emergency-signer any-signer; do
  generate_ed25519_key "${key}"
done

# visible-run-a: canonical-equivalent graph with one edge ordering.
mkdir -p "${RUNS_DIR}/visible-run-a/callbacks"
cat >"${RUNS_DIR}/visible-run-a/graph.json" <<'EOF'
{
  "graph_id": "visible-graph-alpha",
  "graph_type": "undirected",
  "nodes": [{"id": "n1"}, {"id": "n2"}, {"id": "n3"}],
  "edges": [
    {"source": "n1", "target": "n2", "kind": "data", "weight": "1.50", "attributes": {"lane": "primary"}},
    {"source": "n2", "target": "n3", "kind": "data", "weight": "01.0", "attributes": {"lane": "secondary"}}
  ],
  "layout": {"ignored": true}
}
EOF

cat >"${RUNS_DIR}/visible-run-a/run.json" <<'EOF'
{
  "run_id": "visible-run-a",
  "experiment_id": "exp-visible-a",
  "graph_id": "visible-graph-alpha",
  "started_at": "2026-01-10T11:00:00Z",
  "parameters": {"epochs": "3", "lr": "0.01"},
  "tags": {"team": "ml-platform", "tier": "visible"}
}
EOF

cat >"${RUNS_DIR}/visible-run-a/callbacks/01-pending.json" <<'EOF'
{
  "event_id": "evt-a-001",
  "run_id": "visible-run-a",
  "experiment_id": "exp-visible-a",
  "graph_digest": "0000000000000000000000000000000000000000000000000000000000000000",
  "policy_version": "2026.1",
  "schema_version": "2.16.2",
  "status": "PENDING",
  "occurred_at": "2026-01-10T11:00:01Z",
  "metrics": {"queue_depth": 0}
}
EOF

cat >"${RUNS_DIR}/visible-run-a/callbacks/02-running.json" <<'EOF'
{
  "event_id": "evt-a-002",
  "run_id": "visible-run-a",
  "experiment_id": "exp-visible-a",
  "graph_digest": "0000000000000000000000000000000000000000000000000000000000000000",
  "policy_version": "2026.1",
  "schema_version": "2.16.2",
  "status": "RUNNING",
  "occurred_at": "2026-01-10T11:05:00Z",
  "metrics": {"step": 1}
}
EOF

cat >"${RUNS_DIR}/visible-run-a/callbacks/03-finished.json" <<'EOF'
{
  "event_id": "evt-a-003",
  "run_id": "visible-run-a",
  "experiment_id": "exp-visible-a",
  "graph_digest": "0000000000000000000000000000000000000000000000000000000000000000",
  "policy_version": "2026.1",
  "schema_version": "2.16.2",
  "status": "FINISHED",
  "occurred_at": "2026-01-10T11:30:00Z",
  "metrics": {"accuracy": 0.91},
  "artifact_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}
EOF

# visible-run-b: semantically equivalent graph with permuted edge order and endpoint swap.
mkdir -p "${RUNS_DIR}/visible-run-b/callbacks"
cat >"${RUNS_DIR}/visible-run-b/graph.json" <<'EOF'
{
  "graph_type": "undirected",
  "graph_id": "visible-graph-alpha",
  "nodes": [{"id": "n3"}, {"id": "n1"}, {"id": "n2"}],
  "edges": [
    {"source": "n3", "target": "n2", "kind": "data", "weight": "1", "attributes": {"lane": "secondary"}},
    {"source": "n2", "target": "n1", "kind": "data", "weight": "1.5", "attributes": {"lane": "primary"}}
  ]
}
EOF

cat >"${RUNS_DIR}/visible-run-b/run.json" <<'EOF'
{
  "tags": {"tier": "visible", "team": "ml-platform"},
  "parameters": {"lr": "0.01", "epochs": "3"},
  "started_at": "2026-01-10T11:00:00Z",
  "graph_id": "visible-graph-alpha",
  "experiment_id": "exp-visible-a",
  "run_id": "visible-run-b"
}
EOF

cat >"${RUNS_DIR}/visible-run-b/callbacks/01-running.json" <<'EOF'
{
  "event_id": "evt-b-001",
  "run_id": "visible-run-b",
  "experiment_id": "exp-visible-a",
  "graph_digest": "0000000000000000000000000000000000000000000000000000000000000000",
  "policy_version": "2026.1",
  "schema_version": "2.16.2",
  "status": "RUNNING",
  "occurred_at": "2026-01-10T11:00:05Z",
  "metrics": {"step": 0}
}
EOF

cat >"${RUNS_DIR}/visible-run-b/callbacks/02-finished.json" <<'EOF'
{
  "event_id": "evt-b-002",
  "run_id": "visible-run-b",
  "experiment_id": "exp-visible-a",
  "graph_digest": "0000000000000000000000000000000000000000000000000000000000000000",
  "policy_version": "2026.1",
  "schema_version": "2.16.2",
  "status": "FINISHED",
  "occurred_at": "2026-01-10T11:30:00Z",
  "metrics": {"accuracy": 0.91},
  "artifact_digest": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
}
EOF

# Build minimal fake MLflow source tarball with strict upstream callback schema.
STAGING="$(mktemp -d)"
trap 'rm -rf "${STAGING}"' EXIT
mkdir -p "${STAGING}/mlflow/server/graphql/schemas"
if [[ -f "${SCHEMA_SRC}" ]]; then
  cp "${SCHEMA_SRC}" "${STAGING}/mlflow/server/graphql/schemas/run_callback.schema.json"
else
  cat >"${STAGING}/mlflow/server/graphql/schemas/run_callback.schema.json" <<'EOF'
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "MLflow Run Callback",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "event_id",
    "run_id",
    "experiment_id",
    "graph_digest",
    "policy_version",
    "schema_version",
    "status",
    "occurred_at",
    "metrics"
  ],
  "properties": {
    "event_id": {"type": "string", "minLength": 1},
    "run_id": {"type": "string", "minLength": 1},
    "experiment_id": {"type": "string", "minLength": 1},
    "graph_digest": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
    "policy_version": {"type": "string", "minLength": 1},
    "schema_version": {"type": "string", "minLength": 1},
    "status": {
      "type": "string",
      "enum": ["PENDING", "RUNNING", "FINISHED", "FAILED", "KILLED"]
    },
    "occurred_at": {"type": "string", "format": "date-time"},
    "metrics": {"type": "object"},
    "artifact_digest": {"type": "string", "pattern": "^[a-f0-9]{64}$"}
  },
  "allOf": [
    {
      "if": {
        "properties": {
          "status": {"enum": ["FINISHED", "FAILED", "KILLED"]}
        }
      },
      "then": {"required": ["artifact_digest"]}
    }
  ]
}
EOF
fi

TARBALL="${MLFLOW_DIR}/mlflow-2.16.2.tar.gz"
tar -C "${STAGING}" -czf "${TARBALL}" mlflow
sha256sum "${TARBALL}" | awk '{print $1 "  mlflow-2.16.2.tar.gz"}' >"${MLFLOW_DIR}/mlflow-2.16.2.sha256"

# Tampered cache sample for reproduction notes.
mkdir -p "${CACHE_SAMPLE_DIR}/tampered"
cp "${TARBALL}" "${CACHE_SAMPLE_DIR}/tampered/mlflow-2.16.2.tar.gz"
printf '\n' >>"${CACHE_SAMPLE_DIR}/tampered/mlflow-2.16.2.tar.gz"

cat >"${DEST}/fixtures-manifest.txt" <<EOF
runs=${RUNS_DIR}
keys=${KEYS_DIR}
mlflow_release=${MLFLOW_DIR}
tampered_cache=${CACHE_SAMPLE_DIR}/tampered/mlflow-2.16.2.tar.gz
EOF

echo "Visible fixtures written under ${DEST}"
