"""Verifier tests for the NimbusVault Compose trust attestation task."""

import hashlib
import json
import subprocess
from pathlib import Path

APP_DIR = Path("/app")
DB_PATH = APP_DIR / "trust.db"


def run(cmd, *args):
    result = subprocess.run(
        [cmd, *args],
        cwd=APP_DIR,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"{cmd} {' '.join(args)} failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    return result.stdout


def query(sql):
    result = subprocess.run(
        ["sqlite3", "-json", str(DB_PATH), sql],
        text=True,
        capture_output=True,
        check=True,
    )
    payload = result.stdout.strip()
    return json.loads(payload) if payload else []


def trust_ledger_snapshot():
    return {
        "compose_exceptions": query(
            "SELECT exception_id,service,compose_file,rule_code,expires_on,approver,evidence_ref,mount_target,environment,canonical_note "
            "FROM compose_exceptions ORDER BY exception_id"
        ),
        "release_refs": query(
            "SELECT branch,source_ref,observed_at FROM release_refs ORDER BY branch"
        ),
        "changelog_tags": query(
            "SELECT tag,source_ref,signed,observed_at FROM changelog_tags ORDER BY tag"
        ),
        "audit_events": query(
            "SELECT event_key,event_value FROM audit_events ORDER BY event_key"
        ),
    }


def ledger_seal():
    payload = json.dumps(trust_ledger_snapshot(), separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def test_attestor_runs_from_typescript_sources():
    """The TypeScript runner updates trust.db without relying on a prebuilt database."""
    run("npm", "run", "trust:attest")
    assert DB_PATH.exists(), "trust.db was not created"


def test_trust_ledger_snapshot_seal_matches_canonical_ledger():
    """The security ledger snapshot matches the canonical trust ledger seal."""
    assert ledger_seal() == "f7f1ef02d7448e8157e233ab8a4da2ea538c6f9bdfbc8af7186943610d45ebfb"


def test_exception_filtering_uses_latest_status_and_compose_evidence():
    """Latest review status, expiry, and Compose evidence validation decide canonical exceptions."""
    rows = query(
        "SELECT exception_id,service,rule_code,environment FROM compose_exceptions ORDER BY exception_id"
    )
    assert len(rows) == 2
    assert [row["exception_id"] for row in rows] == ["NV-EX-001", "NV-EX-004"]
    leaked = {"NV-EX-002", "NV-EX-003", "NV-EX-005"} & {
        row["exception_id"] for row in rows
    }
    assert not leaked, f"withdrawn, invalid, or expired exception leaked into trust.db: {sorted(leaked)}"


def test_release_branches_and_changelog_tags_are_canonical():
    """Suffix, prefix, RC, draft, and unsigned release near misses are excluded."""
    branches = [
        row["branch"]
        for row in query("SELECT branch FROM release_refs ORDER BY branch")
    ]
    assert branches == ["release/2.27", "release/2.28", "release/2.29"]

    tags = query("SELECT tag,source_ref,signed FROM changelog_tags ORDER BY tag")
    assert [row["tag"] for row in tags] == ["v2.27.4", "v2.28.0", "v2.29.1"]
    tag_228 = next(row for row in tags if row["tag"] == "v2.28.0")
    assert tag_228["source_ref"] == "v2.28.0+in-toto"
    assert tag_228["signed"] == 1


def test_attestor_is_deterministic_on_rerun():
    """Re-running the trust attestation produces the same security ledger snapshot."""
    before = ledger_seal()
    run("npm", "run", "trust:attest")
    after = ledger_seal()
    assert before == after
