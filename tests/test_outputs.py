"""Behavioral verification for harden-rails-compose-archive-attestation."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import requests

from support.archive_factory import build_archive
from support.corpus_fixture import metadata, unpack
from support.integrity import verify_fixture_checksums
from support.puma_server import PumaServer
from support.signature_checks import verify_attestation

FIXTURES = Path(__file__).resolve().parent / "fixtures"
META = metadata()


@pytest.fixture(scope="session", autouse=True)
def _checksums() -> None:
    verify_fixture_checksums()


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "cache"
    d.mkdir()
    return d


def post_attestation(server: PumaServer, archive: bytes, release_ref: str | None = None) -> requests.Response:
    files = {"archive": ("archive.tar", archive, "application/x-tar")}
    data = {}
    if release_ref:
        data["release_ref"] = release_ref
    return requests.post(f"{server.base_url}/api/v1/attestations", files=files, data=data, timeout=60)


def test_health_route_is_preserved(cache_dir: Path) -> None:
    """GET /up remains available."""
    repo = unpack("trusted-corpus-a")
    with PumaServer(remote_url=f"file://{repo}", cache_root=str(cache_dir)) as server:
        resp = requests.get(f"{server.base_url}/up", timeout=10)
        assert resp.status_code == 200


def test_default_trusted_release_clean_archive_passes(cache_dir: Path) -> None:
    """Clean seeded archive returns pass attestation with valid signature."""
    repo = unpack("trusted-corpus-a")
    archive, _ = build_archive(
        11,
        [
            {"name": "compose.yml", "data": "services:\n  web:\n    image: nginx\n"},
            {"name": "app.env", "data": "PUBLIC_URL=https://example.com\n"},
        ],
    )
    with PumaServer(remote_url=f"file://{repo}", cache_root=str(cache_dir)) as server:
        resp = post_attestation(server, archive)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["verdict"] == "pass"
        assert body["findings"] == []
        verify_attestation(dict(body))


def test_mixed_archive_reports_constructed_findings_without_secret_leakage(cache_dir: Path) -> None:
    """Injected violations appear without leaking secret bytes."""
    repo = unpack("trusted-corpus-a")
    secret = "sk_live_abcdefghijklmnop"
    archive, manifest = build_archive(
        22,
        [
            {
                "path": "stack/docker-compose.yml",
                "data": f"services:\n  api:\n    environment:\n      DATABASE_PASSWORD: {secret}\n",
                "expect_finding": True,
                "rule_id": "compose.secret",
            },
            {
                "path": "tokens/bad.jwt",
                "data": "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJhYmMifQ.\n",
                "expect_finding": True,
                "kind": "jwt",
                "rule_id": "jwt.forbidden_algorithm",
            },
        ],
    )
    with PumaServer(remote_url=f"file://{repo}", cache_root=str(cache_dir)) as server:
        resp = post_attestation(server, archive, META["trusted_a"]["ref"])
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["verdict"] == "reject"
        raw = resp.text
        assert secret not in raw
        paths = {f["path"] for f in body["findings"]}
        assert any(m.path in paths for m in manifest)


def test_archive_path_traversal_is_rejected_before_scanning(cache_dir: Path) -> None:
    """Parent-traversing archive paths are rejected with HTTP 422 before scanning."""
    repo = unpack("trusted-corpus-a")
    archive, _ = build_archive(33, [{"path": "../outside.env", "data": "SECRET=1\n"}])
    with PumaServer(remote_url=f"file://{repo}", cache_root=str(cache_dir)) as server:
        resp = post_attestation(server, archive)
        assert resp.status_code == 422
        assert "error" in resp.json()


def test_invalid_or_non_tag_release_refs_are_refused(cache_dir: Path) -> None:
    """Branch refs and other non-tag release references are refused."""
    repo = unpack("trusted-corpus-a")
    archive, _ = build_archive(44, [{"name": "ok.env", "data": "OK=1\n"}])
    with PumaServer(remote_url=f"file://{repo}", cache_root=str(cache_dir)) as server:
        resp = post_attestation(server, archive, META["trusted_a"]["branch_ref"])
        assert resp.status_code in {422, 424}


def test_unsigned_annotated_tag_is_refused(cache_dir: Path) -> None:
    """Unsigned annotated tags return HTTP 424."""
    repo = unpack("unsigned-corpus")
    archive, _ = build_archive(55, [{"name": "ok.env", "data": "OK=1\n"}])
    with PumaServer(remote_url=f"file://{repo}", cache_root=str(cache_dir)) as server:
        resp = post_attestation(server, archive, META["unsigned"]["ref"])
        assert resp.status_code == 424


def test_valid_signature_from_untrusted_fingerprint_is_refused(cache_dir: Path) -> None:
    """Valid signatures from fingerprints outside the allowlist are refused."""
    repo = unpack("untrusted-signer-corpus")
    archive, _ = build_archive(66, [{"name": "ok.env", "data": "OK=1\n"}])
    with PumaServer(remote_url=f"file://{repo}", cache_root=str(cache_dir)) as server:
        resp = post_attestation(server, archive, META["untrusted"]["ref"])
        assert resp.status_code == 424


def test_lfs_policy_is_hydrated_and_controls_results(cache_dir: Path) -> None:
    """Corpus B LFS policy hydration drives scanner findings and policy_sha256."""
    repo = unpack("trusted-corpus-b")
    archive, _ = build_archive(
        77,
        [{"path": "notes.txt", "data": "corp_b_vault_marker\n", "expect_finding": True, "rule_id": "CORPUS-B-VAULT-LINE"}],
    )
    with PumaServer(
        remote_url=f"file://{repo}",
        cache_root=str(cache_dir),
        allowed_signer=META["trusted_b"]["signer_fingerprint"],
    ) as server:
        resp = post_attestation(server, archive, META["trusted_b"]["ref"])
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["baseline"]["policy_sha256"] == META["trusted_b"]["policy_sha256"]


def test_attestation_signature_matches_canonical_payload(cache_dir: Path) -> None:
    """RS256 signature verifies against the canonical unsigned payload."""
    repo = unpack("trusted-corpus-a")
    archive, _ = build_archive(88, [{"name": "bad.env", "data": "API_SECRET=sk_live_qwertyuiopasdfgh\n", "expect_finding": True, "rule_id": "compose.secret"}])
    with PumaServer(remote_url=f"file://{repo}", cache_root=str(cache_dir)) as server:
        resp = post_attestation(server, archive)
        body = resp.json()
        verify_attestation(dict(body))


def test_repeated_identical_request_is_byte_deterministic(cache_dir: Path) -> None:
    """Identical requests produce byte-identical JSON responses."""
    repo = unpack("trusted-corpus-a")
    archive, _ = build_archive(99, [{"name": "compose.yml", "data": "services:\n  web:\n    image: nginx\n"}])
    with PumaServer(remote_url=f"file://{repo}", cache_root=str(cache_dir)) as server:
        bodies = [post_attestation(server, archive).content for _ in range(3)]
        assert bodies[0] == bodies[1] == bodies[2]


def test_existing_rspec_behavior_remains_green() -> None:
    """Shipped RSpec examples continue to pass after the repair."""
    proc = subprocess.run(
        ["bundle", "exec", "rspec", "--format", "progress", "/app/environment/source/spec"],
        cwd="/app",
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
