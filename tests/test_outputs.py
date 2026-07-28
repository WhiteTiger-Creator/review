"""mTLS-to-OIDC trust graph recovery verifiers."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from pathlib import Path

import pytest
import yaml

APP = Path("/app/environment")
POLICY = Path("/output/gateway-policy.yaml")
SUMMARY = Path("/output/migration-summary.json")
AUDIT = Path("/output/migration-audit.db")
PROTECTED = [
    Path("/data/canonical"),
    Path("/data/oidc-contracts"),
    Path("/data/dossier-authority"),
]


def merged_env(extra: dict | None = None) -> dict[str, str]:
    env = os.environ.copy()
    if extra:
        env.update(extra)
    return env


def checksum_tree(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest = subprocess.run(
                ["sha256sum", str(path)],
                text=True,
                capture_output=True,
                check=False,
                env=merged_env(),
            ).stdout.split()[0]
            out[str(path.relative_to(root))] = digest
    return out


@pytest.fixture(scope="module")
def protected_before() -> dict[str, dict[str, str]]:
    return {str(p): checksum_tree(p) for p in PROTECTED}


@pytest.fixture(scope="module", autouse=True)
def run_migration() -> None:
    subprocess.run([str(APP / "bin/reset-state")], check=False, env=merged_env())
    result = subprocess.run(
        [str(APP / "bin/migrate-policy")],
        text=True,
        capture_output=True,
        check=False,
        env=merged_env(),
        cwd="/app",
    )
    assert result.returncode == 0, result.stdout + result.stderr


def load_policy() -> dict:
    assert POLICY.exists()
    return yaml.safe_load(POLICY.read_text(encoding="utf-8"))


def load_summary() -> dict:
    assert SUMMARY.exists()
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def test_outputs_exist() -> None:
    """Migration must emit policy, summary, and audit database outputs."""
    assert POLICY.exists()
    assert SUMMARY.exists()
    assert AUDIT.exists()


def test_summary_schema() -> None:
    """Summary JSON must expose schema_version, run_id, edge_count, and complete status."""
    summary = load_summary()
    assert summary["schema_version"] == 1
    assert summary["status"] == "complete"
    assert summary["edge_count"] > 0


def test_policy_schema_and_semantic_issuer() -> None:
    """Policy must use discovery semantic issuer and JWKS URI rather than loopback transport."""
    policy = load_policy()
    assert policy["schema_version"] == 2
    issuers = policy["issuers"]
    assert "https://accounts.google.com" in issuers
    block = issuers["https://accounts.google.com"]
    assert block["jwks_uri"] == "https://www.googleapis.com/oauth2/v3/certs"
    assert "127.0.0.1" not in block["jwks_uri"]


def test_parallel_edges_distinct() -> None:
    """Parallel api-gateway to user-service edges must remain distinct by environment scope."""
    policy = load_policy()
    prod = [e for e in policy["edges"] if e["source"] == "api-gateway" and e["target"] == "user-service" and e["environment"] == "production"]
    stag = [e for e in policy["edges"] if e["source"] == "api-gateway" and e["target"] == "user-service" and e["environment"] == "staging"]
    assert len(prod) == 1
    assert len(stag) == 1
    assert prod[0]["authz_scope"] != stag[0]["authz_scope"]


def test_alias_resolution() -> None:
    """Graph aliases such as auth-svc must resolve to canonical auth-service identities."""
    policy = load_policy()
    targets = {e["target"] for e in policy["edges"]}
    assert "auth-service" in targets
    assert "auth-svc" not in targets


def test_denied_edge_not_allow() -> None:
    """Explicitly denied payment refund edges must remain deny policies."""
    policy = load_policy()
    denied = [e for e in policy["edges"] if e.get("source") == "api-gateway" and e.get("target") == "payment-service"]
    assert len(denied) == 1
    assert denied[0]["action"] == "deny"


def test_retired_service_excluded() -> None:
    """Retired admin-api must not receive allow policies."""
    policy = load_policy()
    retired_allow_edges = [
        e for e in policy["edges"] if e.get("target") == "admin-api" and e.get("action") == "allow"
    ]
    assert len(retired_allow_edges) == 0


def test_no_retired_mtls_fields() -> None:
    """Generated policy must not retain legacy mTLS certificate fields."""
    text = POLICY.read_text(encoding="utf-8")
    for field in ("client_cert_subject", "ca_bundle", "serial_number", "mtls_trust_bundle"):
        assert field not in text


def test_dossier_authority_beats_superseded() -> None:
    """Accepted dossier decisions must beat newer superseded audience notes."""
    policy = load_policy()
    user_edges = [e for e in policy["edges"] if e.get("target") == "user-service" and e.get("action") == "allow"]
    audiences = {a for e in user_edges for a in e.get("audiences", [])}
    assert "https://users.example.com/v2/prod" in audiences
    assert "https://legacy-users.example.com" not in audiences


def test_safe_algorithms_only() -> None:
    """Allow policies must only advertise safe asymmetric algorithms."""
    policy = load_policy()
    for e in policy["edges"]:
        if e.get("action") == "allow":
            for alg in e.get("algorithms", []):
                assert alg in {"RS256", "ES256"}


def test_audit_complete_run() -> None:
    """Audit database must record a COMPLETE authoritative migration run."""
    conn = sqlite3.connect(AUDIT)
    row = conn.execute("SELECT status FROM latest_complete_run").fetchone()
    assert row is not None
    assert row[0] == "COMPLETE"


def test_coverage_no_gaps() -> None:
    """Recursive coverage view must report zero uncovered deployable edges."""
    conn = sqlite3.connect(AUDIT)
    gaps = conn.execute("SELECT COUNT(*) FROM coverage_gaps").fetchone()[0]
    assert gaps == 0


def test_idempotent_rerun() -> None:
    """Repeated migration runs must produce byte-identical gateway policy YAML."""
    first = POLICY.read_bytes()
    subprocess.run([str(APP / "bin/migrate-policy")], check=False, env=merged_env(), cwd="/app")
    second = POLICY.read_bytes()
    assert first == second


def test_both_oidc_revisions() -> None:
    """Migration must succeed for both bundled OIDC contract revisions."""
    env = merged_env({"OIDC_CONTRACT_REVISION": "google-revision-b"})
    subprocess.run([str(APP / "bin/reset-state")], check=False, env=env)
    result = subprocess.run(
        [str(APP / "bin/migrate-policy")],
        text=True,
        capture_output=True,
        check=False,
        env=env,
        cwd="/app",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    policy = load_policy()
    assert policy["issuers"]["https://accounts.google.com"]["jwks_uri"] == "https://www.googleapis.com/oauth2/v3/certs-rotated"


def test_protected_fixtures_unchanged(protected_before: dict[str, dict[str, str]]) -> None:
    """Canonical and contract trees under /data must remain read-only."""
    for path in PROTECTED:
        assert protected_before[str(path)] == checksum_tree(path)


def test_transport_not_in_policy() -> None:
    """Loopback fixture transport URLs must not appear in effective policy output."""
    text = POLICY.read_text(encoding="utf-8")
    assert "18081" not in text
    assert "127.0.0.1" not in text
