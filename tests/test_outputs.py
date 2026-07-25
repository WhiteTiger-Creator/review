"""Black-box Project Terminus verifier for signingd."""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidSignature
from verifier_lib.job_factory import install_job, make_job
from verifier_lib.output_reader import index, record
from verifier_lib.process_runner import CURRENT, LEGACY, run
from verifier_lib.signature_check import PUBLIC, fingerprint, verify
from verifier_lib.state_factory import write_final, write_journal, write_stage
from verifier_lib.token_factory import create_ambiguous_legacy_token

APP = Path("/app")
QUEUE, PAYLOADS, STATE = APP / "queue", APP / "payloads", APP / "state"
OUTPUT, LOGS = Path("/output/signed"), Path("/var/log/signing")


def _uri_from_current(key_name: str) -> str:
    text = CURRENT.read_text()
    match = re.search(
        rf'\[keys\.{re.escape(key_name)}\]\s*\nuri\s*=\s*"([^"]+)"',
        text,
    )
    assert match, f"missing URI for {key_name} in {CURRENT}"
    return match.group(1)


KEYS = {
    "release-primary": (PUBLIC / "release-primary.pem", lambda: _uri_from_current("release-primary")),
    "release-secondary": (PUBLIC / "release-secondary.pem", lambda: _uri_from_current("release-secondary")),
    "legacy": (PUBLIC / "legacy.pem", lambda: "legacy:token=legacy-token;object=legacy-signing"),
}


@pytest.fixture(autouse=True)
def clean_runtime() -> None:
    """Give every scenario fresh queue, durable state, publication, and logs."""
    for directory in (QUEUE, PAYLOADS, STATE, OUTPUT, LOGS):
        shutil.rmtree(directory, ignore_errors=True)
    for directory in (QUEUE, PAYLOADS, STATE, OUTPUT / "jobs", LOGS):
        directory.mkdir(parents=True, exist_ok=True)


def assert_success(result) -> None:
    assert result.returncode == 0, f"signingd failed:\nstdout={result.stdout}\nstderr={result.stderr}"


def assert_record(job: dict[str, object], payload: bytes, *, key: str | None = None) -> dict[str, object]:
    """Assert all signed-record fields, identity data, and cryptographic validity."""
    chosen = key or str(job["key"])
    pem, uri_fn = KEYS[chosen]
    uri = uri_fn() if callable(uri_fn) else uri_fn
    signed = record(str(job["job_id"]))
    assert set(signed) == {"schema_version", "job_id", "payload_sha256", "key", "key_uri",
                           "key_fingerprint_sha256", "mechanism", "signature_base64", "status"}
    assert signed["schema_version"] == 1
    assert signed["job_id"] == job["job_id"]
    assert signed["payload_sha256"] == hashlib.sha256(payload).hexdigest()
    assert signed["key"] == chosen and signed["key_uri"] == uri
    assert signed["key_fingerprint_sha256"] == fingerprint(pem)
    assert signed["mechanism"] == job["mechanism"] and signed["status"] == "signed"
    verify(signed, payload, pem)
    return signed


def assert_index(job_ids: set[str]) -> None:
    """Assert index completeness, exact set membership, and deterministic ordering."""
    data = index()
    assert set(data) == {"schema_version", "jobs"} and data["schema_version"] == 1
    jobs = data["jobs"]
    assert {item["job_id"] for item in jobs} == job_ids
    assert [item["job_id"] for item in jobs] == sorted(job_ids)
    assert {item["record"] for item in jobs} == {f"jobs/{job_id}.json" for job_id in job_ids}
    for item in jobs:
        signed = record(item["job_id"])
        assert item["payload_sha256"] == signed["payload_sha256"]
        assert item["key_fingerprint_sha256"] == signed["key_fingerprint_sha256"]


def test_current_config_signs_three_canonical_records() -> None:
    """Current configuration signs three jobs with canonical records and index."""
    jobs = [
        make_job("normal-a", b"alpha\x00", mechanism="rsa-pss-sha256"),
        make_job("normal-b", b"bravo", mechanism="rsa-pkcs1-sha256"),
        make_job("normal-c", b"charlie", key="release-secondary"),
    ]
    for ordinal, job in enumerate(reversed(jobs)):
        install_job(job, f"{ordinal:03d}-fixture.json")
    assert_success(run())
    for job, payload in zip(jobs, (b"alpha\x00", b"bravo", b"charlie")):
        assert_record(job, payload)
    assert_index({str(job["job_id"]) for job in jobs})


def test_worker_replacement_preserves_key_identity() -> None:
    """One-job workers retain configured key identity without leaking handles."""
    jobs = [make_job(f"replace-{i}", f"payload-{i}".encode()) for i in range(3)]
    for job in jobs:
        install_job(job)
    assert_success(run())
    for i, job in enumerate(jobs):
        signed = assert_record(job, f"payload-{i}".encode())
        assert "handle" not in str(signed).lower()
        assert signed["key_uri"] == KEYS["release-primary"][1]()
    assert_index({str(job["job_id"]) for job in jobs})


def test_full_restart_uses_durable_completion_state() -> None:
    """A restart preserves completed records and signs only newly queued work."""
    first = make_job("restart-first", b"first")
    install_job(first)
    assert_success(run())
    before = (OUTPUT / "jobs/restart-first.json").read_bytes()
    second = make_job("restart-second", b"second", mechanism="rsa-pkcs1-sha256")
    install_job(second)
    assert_success(run())
    assert (OUTPUT / "jobs/restart-first.json").read_bytes() == before
    assert_record(first, b"first")
    assert_record(second, b"second")
    assert_index({"restart-first", "restart-second"})


def test_current_uri_selects_secondary_not_primary_fallback() -> None:
    """A secondary URI selects its exact key and cannot verify against primary."""
    job = make_job("secondary-only", b"secondary", key="release-secondary")
    install_job(job)
    assert_success(run())
    signed = assert_record(job, b"secondary")
    with pytest.raises(InvalidSignature):
        verify(signed, b"secondary", KEYS["release-primary"][0])


def test_legacy_configuration_is_supported() -> None:
    """Legacy label selection signs with the documented legacy key URI."""
    job = make_job("legacy-good", b"legacy payload", key="legacy")
    install_job(job)
    assert_success(run(LEGACY))
    assert_record(job, b"legacy payload")
    assert_index({"legacy-good"})


def test_ambiguous_legacy_selection_is_rejected(tmp_path: Path) -> None:
    """Legacy config rejects a token holding two same-label private keys."""
    conf, _ = create_ambiguous_legacy_token(tmp_path)
    config = tmp_path / "legacy.toml"
    config.write_text(
        '''schema_version = 1
module = "/usr/lib/softhsm/libsofthsm2.so"
pin_file = "/app/config/token-user.pin"
token_label = "legacy-token"
key_label = "legacy-signing"
public_key = "/app/config/public/legacy.pem"
state_dir = "/app/state"
queue_dir = "/app/queue"
payload_root = "/app/payloads"
output_dir = "/output/signed"
log_dir = "/var/log/signing"
''')
    job = make_job("legacy-ambiguous", b"must not sign", key="legacy")
    install_job(job)
    result = run(config, softhsm_conf=conf)
    assert result.returncode != 0
    assert not (OUTPUT / "jobs/legacy-ambiguous.json").exists()


def test_recovers_a_valid_staged_signature() -> None:
    """Startup publishes a valid staged signed record without re-signing it."""
    job = make_job("recover-stage", b"staged")
    install_job(job)
    assert_success(run())
    signed = record("recover-stage")
    shutil.rmtree(OUTPUT)
    shutil.rmtree(STATE)
    write_stage(job, signed)
    write_journal()
    assert_success(run())
    assert_record(job, b"staged")
    assert_index({"recover-stage"})


def test_recovers_final_record_missing_index() -> None:
    """Startup reconstructs an index when a valid final record already exists."""
    job = make_job("recover-final", b"final")
    install_job(job)
    assert_success(run())
    signed = record("recover-final")
    shutil.rmtree(OUTPUT)
    shutil.rmtree(STATE)
    write_final(signed)
    write_journal()
    assert_success(run())
    assert_record(job, b"final")
    assert_index({"recover-final"})


def test_conflicting_job_id_is_rejected_and_original_survives() -> None:
    """A reused job ID with a different body fails without replacing output."""
    first = make_job("conflict-id", b"original")
    install_job(first, "001-original.json")
    assert_success(run())
    original = (OUTPUT / "jobs/conflict-id.json").read_bytes()
    second = make_job("conflict-id", b"replacement", payload_path=PAYLOADS / "replacement.bin")
    install_job(second, "999-conflict.json")
    assert run().returncode != 0
    assert (OUTPUT / "jobs/conflict-id.json").read_bytes() == original
    assert_record(first, b"original")
    assert_index({"conflict-id"})


def test_unsupported_mechanism_has_no_partial_publication() -> None:
    """An unsupported mechanism exits unsuccessfully and publishes no job record."""
    job = make_job("unsupported", b"no publication", mechanism="rsa-sha512")
    install_job(job)
    assert run().returncode != 0
    assert not (OUTPUT / "jobs/unsupported.json").exists()
    if (OUTPUT / "index.json").exists():
        assert "unsupported" not in {entry["job_id"] for entry in index()["jobs"]}


def test_sensitive_material_never_reaches_outputs_or_logs() -> None:
    """PIN and private-key markers do not appear in published files or logs."""
    job = make_job("secret-scan", b"secret scan")
    install_job(job)
    assert_success(run())
    haystack = b"".join(path.read_bytes() for root in (OUTPUT, LOGS) for path in root.rglob("*") if path.is_file())
    assert b"123456" not in haystack
    assert b"BEGIN PRIVATE KEY" not in haystack
    assert b"BEGIN RSA PRIVATE KEY" not in haystack


def test_generated_scenario_rejects_hardcoded_sample_answers() -> None:
    """Fresh generated IDs and bytes produce valid independent signatures."""
    payload = bytes(range(256)) + b"\x00generated-not-sample\xff"
    job = make_job("generated-z9_42", payload, key="release-secondary", mechanism="rsa-pkcs1-sha256")
    install_job(job, "777-unrelated-name.json")
    assert_success(run())
    assert_record(job, payload)
    assert_index({"generated-z9_42"})
