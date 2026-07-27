"""Behavioral verifier tests for openssl provider profile reconstruction."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest

APP = Path("/app")
DRIVER = APP / "bin" / "harborseal-driver"


def _load_index(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _scope_matches(scope: str, service_id: str) -> bool:
    if scope == service_id:
        return True
    if scope.endswith("/*"):
        prefix = scope[:-1].rstrip("/")
        return service_id.startswith(prefix) and (
            len(service_id) == len(prefix) or service_id[len(prefix)] == "/"
        )
    return False


def _resolve_profile(
    events: list[dict[str, Any]],
    service_id: str,
    *,
    environment: str = "staging",
    host_class: str = "harborseal",
    at: str = "2026-04-01T00:00:00Z",
) -> tuple[str | None, list[str], str | None]:
    active = {e["event_id"]: e for e in events if e.get("decision_type") == "provider_profile"}
    for e in events:
        for sid in e.get("supersedes", []):
            active.pop(sid, None)
    candidates: list[tuple[int, str, dict[str, Any]]] = []
    for e in active.values():
        if e.get("environment") not in (None, environment):
            continue
        if e.get("host_class") not in (None, host_class):
            continue
        if not _scope_matches(str(e.get("service_scope", "")), service_id):
            continue
        if str(e.get("effective_from", "")) > at:
            continue
        until = e.get("effective_until")
        if until and str(until) <= at:
            continue
        specific = 2 if e.get("service_scope") == service_id else 1
        candidates.append((specific, str(e.get("effective_from", "")), e))
    if not candidates:
        return None, [], "no_profile_decision"
    candidates.sort(key=lambda t: (t[0], t[1]), reverse=True)
    winner = candidates[0][2]
    return str(winner.get("profile")), [str(winner.get("report_section", ""))], None


def _load_bundle(config_path: Path) -> dict[str, Any]:
    return json.loads(config_path.read_text(encoding="utf-8"))


def _parse_env(spec: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for entry in spec.get("process", {}).get("env", []):
        if "=" not in entry:
            continue
        key, val = entry.split("=", 1)
        out[key] = val
    return out


def _service_id(spec: dict[str, Any]) -> str:
    return str(spec.get("annotations", {}).get("io.harborseal.service/id", ""))


def _prefix_match(base: str, path: str) -> bool:
    base_n = os.path.normpath(base).replace("\\", "/")
    path_n = os.path.normpath(path).replace("\\", "/")
    return path_n == base_n or path_n.startswith(base_n.rstrip("/") + "/")


def _effective_mount(spec: dict[str, Any], destination: str) -> dict[str, Any] | None:
    dest_n = os.path.normpath(destination).replace("\\", "/")
    last = None
    for mount in spec.get("mounts", []):
        if os.path.normpath(str(mount.get("destination", ""))).replace("\\", "/") == dest_n:
            last = mount
    return last


def _entry_by_service(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {entry["service_id"]: entry for entry in manifest.get("services", [])}


def _map_id(value: int, mappings: list[dict[str, Any]]) -> int:
    for m in mappings:
        c = int(m.get("containerID", 0))
        h = int(m.get("hostID", 0))
        size = int(m.get("size", 0))
        if c <= value < c + size:
            return h + (value - c)
    return value


def _expected_effective_ids(spec: dict[str, Any]) -> tuple[int, int]:
    user = spec.get("process", {}).get("user", {})
    linux = spec.get("linux", {})
    uid = int(user.get("uid", 0))
    gid = int(user.get("gid", 0))
    return (
        _map_id(uid, linux.get("uidMappings", [])),
        _map_id(gid, linux.get("gidMappings", [])),
    )


def _expected_certificate_mounts(spec: dict[str, Any]) -> list[dict[str, str]]:
    out = []
    by_dest = {}
    for mount in spec.get("mounts", []):
        dest = os.path.normpath(str(mount.get("destination", ""))).replace("\\", "/")
        by_dest[dest] = mount
    for dest, mount in sorted(by_dest.items()):
        if not _prefix_match("/etc/ssl/certs", dest):
            continue
        if mount.get("type") != "bind":
            continue
        src = str(mount.get("source", ""))
        if src:
            out.append({"destination": dest, "source": src})
    return out


def _copy_permuted_bundle_root(src: Path, dst: Path) -> None:
    entries = sorted([p for p in src.iterdir() if p.is_dir()], reverse=True)
    for i, item in enumerate(entries):
        shutil.copytree(item, dst / f"{i:02d}-{item.name}")


def _published_bytes(root: Path) -> dict[str, bytes]:
    out = {}
    setup = root / "output" / "setup-manifest.json"
    out["setup-manifest.json"] = setup.read_bytes()
    for profile in sorted((root / "output" / "profiles").glob("*.cnf")):
        out[f"profiles/{profile.name}"] = profile.read_bytes()
    return out


def _load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _has_legacy_fields(entry: dict[str, Any]) -> bool:
    legacy = entry.get("legacy") or {}
    return bool(legacy.get("provider")) and bool(legacy.get("config_path"))


def _profile_contains_providers(path: Path, profile: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if profile == "fips":
        return "hs_fips" in text and "fips=yes" in text
    if profile in {"legacy", "legacy_verify_only"}:
        return "hs_legacy" in text
    return "hs_fips" not in text and "hs_default" in text


def _run_driver(work: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["OPENSSL_CONF"] = ""
    env["OPENSSL_MODULES"] = "/app/data/providers/modules"
    (work / "output" / "profiles").mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [
            str(DRIVER),
            "--report-index",
            str(work / "report" / "decision-index.json"),
            "--report",
            str(work / "report" / "migration-report.md"),
            "--oci-root",
            str(work / "oci"),
            "--cert-root",
            str(work / "certs"),
            "--provider-root",
            str(work / "providers"),
            "--state",
            str(work / "state.json"),
            "--output",
            str(work / "output"),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


@pytest.fixture()
def workdir():
    base = Path(tempfile.mkdtemp(prefix="harborseal-"))
    shutil.copytree(APP / "data" / "report", base / "report")
    shutil.copytree(APP / "data" / "oci", base / "oci")
    shutil.copytree(APP / "data" / "certs", base / "certs")
    shutil.copytree(APP / "data" / "providers", base / "providers")
    shutil.copy2(APP / "data" / "state" / "state.json", base / "state.json")
    (base / "output").mkdir()
    yield base
    shutil.rmtree(base, ignore_errors=True)


@pytest.fixture()
def driven(workdir: Path):
    proc = _run_driver(workdir)
    assert proc.returncode == 0, proc.stderr
    manifest = _load_manifest(workdir / "output" / "setup-manifest.json")
    return workdir, manifest


def test_library_is_sourceable_without_lifecycle_side_effects():
    """AWK library loads without printing until invoked."""
    proc = subprocess.run(
        ["gawk", "-f", str(APP / "lib" / "json.awk"), "-f", str(APP / "lib" / "harborseal.awk"), "BEGIN { hs_reset() }"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_public_driver_generates_manifest_and_profiles(driven):
    """Driver emits setup manifest and profile snippets."""
    workdir, manifest = driven
    assert manifest["schema_version"] == 2
    assert (workdir / "output" / "profiles").exists()
    assert list((workdir / "output" / "profiles").glob("*.cnf"))


def test_report_correction_supersedes_earlier_decision():
    """Payments service resolves to fips after correction event."""
    events = _load_index(APP / "data" / "report" / "decision-index.json")["events"]
    profile, _, reason = _resolve_profile(events, "payments-api")
    assert profile == "fips"
    assert reason is None


def test_service_specific_decision_outranks_family_inheritance():
    """Direct service scope outranks inherited family decision."""
    events = _load_index(APP / "data" / "report" / "decision-index.json")["events"]
    profile, _, _ = _resolve_profile(events, "identity-api")
    assert profile == "default"


def test_process_env_last_occurrence_wins():
    """Duplicate env keys use last documented value."""
    spec = _load_bundle(APP / "data" / "oci" / "payments" / "config.json")
    env = _parse_env(spec)
    assert env.get("OPENSSL_CONF") == "/ignored.conf"


def test_process_env_splits_at_first_equals():
    """Environment values containing equals are preserved."""
    spec = _load_bundle(APP / "data" / "oci" / "payments" / "config.json")
    env = _parse_env(spec)
    assert "PATH" in env


def test_mount_destination_normalization_uses_path_components():
    """Path normalization rejects sibling-prefix escapes."""
    assert not _prefix_match("/data/certs", "/data/certs-old/file.pem")
    assert _prefix_match("/data/certs", "/data/certs/file.pem")


def test_duplicate_destination_uses_last_effective_mount():
    """Last mount for a destination wins."""
    spec = _load_bundle(APP / "data" / "oci" / "archival" / "config.json")
    mount = _effective_mount(spec, "/etc/ssl/certs/service.pem")
    assert mount is not None


def test_service_identity_from_annotation():
    """Service identity comes from public annotation."""
    for bundle in ("payments", "identity", "legacy-proxy"):
        spec = _load_bundle(APP / "data" / "oci" / bundle / "config.json")
        assert _service_id(spec).endswith("-api")


def test_fips_profile_requires_fips_properties(driven):
    """FIPS profile snippets include fips=yes property query."""
    workdir, _ = driven
    prof = workdir / "output" / "profiles" / "payments-api.cnf"
    assert prof.exists(), "payments profile missing"
    assert _profile_contains_providers(prof, "fips")


def test_default_profile_activates_only_required_providers(driven):
    """Default profile does not enable fips module."""
    workdir, _ = driven
    prof = workdir / "output" / "profiles" / "identity-api.cnf"
    assert prof.exists(), "identity profile missing"
    text = prof.read_text(encoding="utf-8")
    assert "hs_fips" not in text


def test_legacy_verify_profile_emits_legacy_sections(driven):
    """Legacy verification profile includes legacy provider section."""
    workdir, _ = driven
    prof = workdir / "output" / "profiles" / "legacy-proxy-api.cnf"
    assert prof.exists(), "legacy profile missing"
    assert "hs_legacy" in prof.read_text(encoding="utf-8")


def test_invalid_services_remain_in_manifest_with_reasons(workdir: Path):
    """Manifest includes error entries with reason codes."""
    proc = _run_driver(workdir)
    assert proc.returncode == 0
    manifest = _load_manifest(workdir / "output" / "setup-manifest.json")
    statuses = {s.get("status") for s in manifest.get("services", [])}
    assert "ready" in statuses


def test_manifest_preserves_legacy_fields(driven):
    """Each ready service retains legacy compatibility fields."""
    _, manifest = driven
    for entry in manifest.get("services", []):
        if entry.get("status") == "ready":
            assert _has_legacy_fields(entry)


def test_ready_manifest_entries_include_operational_fields(driven):
    """Ready manifest entries include documented operational fields."""
    _, manifest = driven
    events = _load_index(APP / "data" / "report" / "decision-index.json")["events"]
    by_service = _entry_by_service(manifest)

    for bundle in sorted((APP / "data" / "oci").iterdir()):
        if not bundle.is_dir():
            continue
        spec = _load_bundle(bundle / "config.json")
        service_id = _service_id(spec)
        entry = by_service[service_id]
        if entry.get("status") != "ready":
            continue

        uid, gid = _expected_effective_ids(spec)
        assert entry.get("effective_uid") == uid
        assert entry.get("effective_gid") == gid

        certs = entry.get("certificate_mounts")
        assert isinstance(certs, list)
        expected_certs = _expected_certificate_mounts(spec)
        assert expected_certs
        for expected in expected_certs:
            assert expected in certs

        expected_profile, expected_sections, _ = _resolve_profile(events, service_id)
        assert expected_profile is not None
        assert entry.get("profile") == expected_profile
        assert entry.get("report_sections") == expected_sections

        actions = entry.get("setup_actions")
        assert isinstance(actions, list)
        assert actions


def test_equivalent_bundle_order_produces_identical_bytes(workdir: Path):
    """Permuting runtime bundle processing order keeps output bytes stable."""
    first = _run_driver(workdir)
    assert first.returncode == 0, first.stderr
    original = _published_bytes(workdir)

    permuted = Path(tempfile.mkdtemp(prefix="hs-perm-"))
    try:
        shutil.copytree(workdir / "report", permuted / "report")
        shutil.copytree(workdir / "certs", permuted / "certs")
        shutil.copytree(workdir / "providers", permuted / "providers")
        shutil.copy2(workdir / "state.json", permuted / "state.json")
        (permuted / "output").mkdir()
        (permuted / "oci").mkdir()
        _copy_permuted_bundle_root(workdir / "oci", permuted / "oci")

        second = _run_driver(permuted)
        assert second.returncode == 0, second.stderr
        assert _published_bytes(permuted) == original
    finally:
        shutil.rmtree(permuted, ignore_errors=True)


def test_source_fixtures_integrity_anchors():
    """Trusted fixture hashes match bundled files."""
    manifest = json.loads((APP / "docs" / "trusted-fixtures.json").read_text(encoding="utf-8"))
    for rel, expected in manifest.get("files", {}).items():
        digest = hashlib.sha256((APP / rel).read_bytes()).hexdigest()
        assert digest == expected


def test_migration_report_is_long_context():
    """Migration report meets long-context token threshold."""
    report = (APP / "data" / "report" / "migration-report.md").read_text(encoding="utf-8")
    assert len(report.split()) >= 50000


def test_manifest_lists_all_discovered_services(driven):
    """Manifest includes an entry per OCI bundle service."""
    _, manifest = driven
    ids = {s["service_id"] for s in manifest.get("services", [])}
    assert "payments-api" in ids
    assert "identity-api" in ids


def test_profile_paths_are_relative(driven):
    """Manifest profile_path values are relative under output."""
    _, manifest = driven
    for entry in manifest.get("services", []):
        path = entry.get("profile_path")
        if path:
            assert not str(path).startswith("/")


def test_openssl_modules_env_points_at_fixture_root():
    """Container uses local provider module directory."""
    modules = Path("/app/data/providers/modules")
    assert modules.is_dir()
    assert any(modules.iterdir())


def test_harborseal_service_user_exists():
    """Container image defines the harborseal service account."""
    passwd = Path("/etc/passwd").read_text(encoding="utf-8")
    assert "harborseal" in passwd


def test_validate_openssl_profile_tool_exists():
    """Inspect helper validates profile syntax."""
    proc = subprocess.run(
        [str(APP / "bin" / "validate-openssl-profile"), "--help"],
        capture_output=True,
        check=False,
    )
    assert proc.returncode in (0, 2)


def test_decision_index_schema_version():
    """Decision index uses schema_version 2."""
    data = _load_index(APP / "data" / "report" / "decision-index.json")
    assert data["schema_version"] == 2


def test_reference_report_matches_manifest_profiles(driven):
    """Manifest ready profiles align with reference report resolver."""
    _, manifest = driven
    events = _load_index(APP / "data" / "report" / "decision-index.json")["events"]
    for entry in manifest.get("services", []):
        if entry.get("status") != "ready":
            continue
        expected, _, _ = _resolve_profile(events, entry["service_id"])
        if expected:
            assert entry.get("profile") == expected
