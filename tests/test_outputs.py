import hashlib
import json
import shutil
import subprocess
from pathlib import Path

APP = Path("/app")
ROOT = APP / "environment"
BIN = APP / "bin" / "collectorctl"
REPORT = APP / "output" / "collector-compliance-report.json"
TRACE = APP / "output" / "collector-runtime-trace.json"
MANIFEST = ROOT / "generated" / "exporter.manifest"
EXPECTED_HASH_FILE = ROOT / "var" / "lib" / "collectorctl.sha256"


def run_ctl(*args, check=True):
    result = subprocess.run(
        [str(BIN), *args],
        cwd=str(APP),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"collectorctl {' '.join(args)} failed with {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


def parse_manifest(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def load_report() -> dict:
    return json.loads(REPORT.read_text(encoding="utf-8"))


def load_trace() -> dict:
    return json.loads(TRACE.read_text(encoding="utf-8"))


def canonical_json(path: Path) -> str:
    return json.dumps(
        json.loads(path.read_text(encoding="utf-8")),
        sort_keys=True,
        separators=(",", ":"),
    )


def test_collectorctl_identity_is_preserved():
    """The shipped operator binary remains the same recorder that the image built."""
    expected = EXPECTED_HASH_FILE.read_text(encoding="utf-8").split()[0]
    actual = hashlib.sha256(BIN.read_bytes()).hexdigest()
    assert actual == expected


def test_regenerated_manifest_matches_visible_authorities(tmp_path):
    """The on-disk manifest is the deterministic export of the current unit, yaml, and tmpfiles authority set."""
    expected = tmp_path / "expected.manifest"
    run_ctl("manifest", "--root", str(ROOT), "--out", str(expected))
    assert MANIFEST.read_text(encoding="utf-8") == expected.read_text(encoding="utf-8")
    values = parse_manifest(MANIFEST)
    assert values["schema"] == "telemetry.collector.exporter.v2"
    assert values["authority"] == "systemd"
    assert values["socket_path"] == "/run/telemetry/collector.sock"
    assert values["socket_user"] == "collector-sink"
    assert values["socket_group"] == "collector-sink"
    assert values["socket_mode"] == "0660"
    assert values["service_socket"] == "collector.socket"
    assert values["service_socket_mode"] == "systemd"
    assert values["tmpfiles_socket_owner"] == "collector-sink"
    assert values["tmpfiles_socket_group"] == "collector-sink"
    assert values["tmpfiles_socket_mode"] == "0660"
    assert values["sink_owner"] == "collector-sink"
    assert values["provenance"] == "regenerated-from-visible-authorities"


def test_lifecycle_report_uses_systemd_socket_through_reload_and_rotation():
    """Lifecycle replay observes one systemd socket authority through reload, activation, restart, rotation, and regeneration."""
    run_ctl("manifest", "--root", str(ROOT), "--out", str(MANIFEST))
    run_ctl(
        "lifecycle", "--root", str(ROOT), "--report", str(REPORT), "--trace", str(TRACE)
    )
    report = load_report()
    trace = load_trace()
    assert report["ok"] is True
    assert report["runtime"]["authority"] == "systemd"
    assert report["runtime"]["socket_path"] == "/run/telemetry/collector.sock"
    assert report["runtime"]["socket_owner"] == "collector-sink"
    assert report["runtime"]["socket_group"] == "collector-sink"
    assert report["runtime"]["socket_mode"] == "0660"
    assert report["manifest"]["consistent"] is True
    for key in [
        "generated_manifest_current",
        "runtime_socket_matches_manifest",
        "socket_owned_by_collector_sink",
        "tmpfiles_preserve_socket_owner",
        "service_binds_declared_socket",
        "main_systemd_socket_authority",
        "main_socket_mode_expected",
        "tmpfiles_directory_owned",
        "lifecycle_socket_inode_stable",
    ]:
        assert report["checks"][key] is True, key
    expected_phases = [
        "daemon-reload",
        "first-activation",
        "service-restart",
        "sink-rotation",
        "report-regeneration",
    ]
    assert [phase["phase"] for phase in report["lifecycle"]] == expected_phases
    assert len({phase["socket_inode"] for phase in report["lifecycle"]}) == 1
    assert trace["stable_inode"] is True
    assert trace["runtime_socket"]["authority"] == "systemd"


def test_report_regenerates_deterministically_after_artifact_removal(tmp_path):
    """Removing generated surfaces and replaying the commands yields byte-equivalent structured reports."""
    for target in [MANIFEST, REPORT, TRACE]:
        target.unlink(missing_ok=True)
    first_report = tmp_path / "first-report.json"
    first_trace = tmp_path / "first-trace.json"
    second_report = tmp_path / "second-report.json"
    second_trace = tmp_path / "second-trace.json"
    run_ctl("manifest", "--root", str(ROOT), "--out", str(MANIFEST))
    run_ctl(
        "lifecycle",
        "--root",
        str(ROOT),
        "--report",
        str(first_report),
        "--trace",
        str(first_trace),
    )
    MANIFEST.unlink(missing_ok=True)
    run_ctl("manifest", "--root", str(ROOT), "--out", str(MANIFEST))
    run_ctl(
        "lifecycle",
        "--root",
        str(ROOT),
        "--report",
        str(second_report),
        "--trace",
        str(second_trace),
    )
    assert canonical_json(first_report) == canonical_json(second_report)
    assert canonical_json(first_trace) == canonical_json(second_trace)


def test_legacy_yaml_fallback_survives_without_socket_unit(tmp_path):
    """The compatibility root has no socket unit, so yaml bind_path remains the runtime authority there."""
    legacy_src = ROOT / "fixtures" / "legacy-root"
    legacy = tmp_path / "legacy-root"
    shutil.copytree(legacy_src, legacy)
    manifest = legacy / "generated" / "exporter.manifest"
    report = tmp_path / "legacy-report.json"
    trace = tmp_path / "legacy-trace.json"
    run_ctl("manifest", "--root", str(legacy), "--out", str(manifest))
    run_ctl(
        "lifecycle",
        "--root",
        str(legacy),
        "--report",
        str(report),
        "--trace",
        str(trace),
    )
    values = parse_manifest(manifest)
    legacy_report = json.loads(report.read_text(encoding="utf-8"))
    legacy_trace = json.loads(trace.read_text(encoding="utf-8"))
    assert values["authority"] == "collector.yaml"
    assert values["socket_path"] == "/run/legacy-collector.sock"
    assert legacy_report["ok"] is True
    assert legacy_report["runtime"]["authority"] == "collector.yaml"
    assert legacy_report["runtime"]["socket_path"] == "/run/legacy-collector.sock"
    assert legacy_report["checks"]["legacy_yaml_fallback_allowed"] is True
    assert legacy_report["checks"]["legacy_fallback_path_present"] is True
    assert legacy_trace["runtime_socket"]["authority"] == "collector.yaml"
