"""Behavioral verifier for msrv-lock-recovery-planner.

Each test builds a minimal or mutated dataset that exercises one rule from
`/app/docs/cargo_recovery_profile.md`, runs the candidate binary, and asserts
focused projections of the report.
"""

from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from reference.canonical import digest_of, sha256_hex
from reference.models import load_dataset
from reference.planner import process_request
from reference.self_checks import run_self_checks
from reference.versions import Requirement, Version

TOP_LEVEL_KEYS = [
    "request_rows",
    "package_selection_rows",
    "patch_rows",
    "source_replacement_rows",
    "lock_entry_rows",
    "invalidation_rows",
    "conflict_rows",
    "summary",
]

BIN = Path(os.environ["MSRV_LOCK_RECOVERY_PLANNER_BIN"])

_CANON_CANDIDATE = Path("/app/data")
if _CANON_CANDIDATE.is_dir():
    CANON_DATA = _CANON_CANDIDATE
else:
    CANON_DATA = Path(__file__).resolve().parents[1] / "environment" / "app" / "data"

DEFAULT_POLICY = {
    "maximum_packages": 64,
    "maximum_dependency_edges": 256,
    "maximum_resolution_rounds": 32,
    "maximum_requests": 16,
    "maximum_workspace_members_per_request": 8,
}


# ---------------------------------------------------------------------------
# Session-wide self-check gate for the Python reference implementation.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _validate_reference_implementation() -> None:
    """Run private reference self-checks once before any candidate test."""
    run_self_checks()


@pytest.fixture(scope="session")
def binary() -> Path:
    assert BIN.is_file(), f"missing candidate binary: {BIN}"
    assert os.access(BIN, os.X_OK), f"candidate binary not executable: {BIN}"
    return BIN


# ---------------------------------------------------------------------------
# Generic dataset construction helpers.
# ---------------------------------------------------------------------------


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def _write_ndjson(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(r, separators=(",", ":")) for r in rows) + "\n",
        encoding="utf-8",
    )


def write_dataset(
    data_dir: Path,
    *,
    workspace_members: list[dict[str, Any]],
    requests: list[dict[str, Any]],
    resolver_mode: str = "fallback",
    workspace_name: str = "test-workspace",
    registry: list[dict[str, Any]] | None = None,
    patched: list[dict[str, Any]] | None = None,
    patch_sets: list[dict[str, Any]] | None = None,
    replacement_sets: list[dict[str, Any]] | None = None,
    locks: list[dict[str, Any]] | None = None,
    policy: dict[str, Any] | None = None,
) -> Path:
    """Write a complete, structurally valid dataset to `data_dir`."""
    data_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        data_dir / "workspace.json",
        {
            "workspace_name": workspace_name,
            "resolver_mode": resolver_mode,
            "members": workspace_members,
        },
    )
    _write_json(data_dir / "registry_packages.json", registry or [])
    _write_json(data_dir / "patched_packages.json", patched or [])
    _write_json(
        data_dir / "patch_sets.json",
        patch_sets if patch_sets is not None else [{"patch_set_id": "ps-empty", "patches": []}],
    )
    _write_json(
        data_dir / "replacement_sources.json",
        replacement_sets
        if replacement_sets is not None
        else [{"replacement_set_id": "rs-empty", "mappings": [], "replacement_records": []}],
    )
    _write_json(
        data_dir / "previous_locks.json",
        locks
        if locks is not None
        else [
            {
                "lock_id": "lock-empty",
                "workspace_digest": "0" * 64,
                "patch_set_digest": "0" * 64,
                "replacement_set_digest": "0" * 64,
                "selected_packages": [],
            }
        ],
    )
    _write_ndjson(data_dir / "build_requests.ndjson", requests)
    _write_json(data_dir / "policy.json", policy or DEFAULT_POLICY)
    return data_dir


def dep(package_name: str, requirement: str, source_id: str = "crates-io") -> dict[str, str]:
    return {"package_name": package_name, "source_id": source_id, "requirement": requirement}


def member(
    member_id: str,
    dependencies: list[dict[str, str]],
    *,
    package_name: str | None = None,
    package_version: str = "0.1.0",
    rust_version: str = "1.0.0",
) -> dict[str, Any]:
    return {
        "member_id": member_id,
        "package_name": package_name or member_id,
        "package_version": package_version,
        "rust_version": rust_version,
        "dependencies": dependencies,
    }


def reg_pkg(
    package_name: str,
    version: str,
    *,
    rust_version: str = "1.0.0",
    yanked: bool = False,
    checksum: str | None = None,
    source_id: str = "crates-io",
    dependencies: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "package_name": package_name,
        "version": version,
        "source_id": source_id,
        "checksum": checksum or sha256_hex(f"{source_id}:{package_name}:{version}"),
        "rust_version": rust_version,
        "yanked": yanked,
        "dependencies": dependencies or [],
    }


def request_row(
    request_id: str,
    member_ids: list[str],
    *,
    lock_id: str = "lock-empty",
    patch_set_id: str = "ps-empty",
    replacement_set_id: str = "rs-empty",
    lockfile_mode: str = "update",
) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "lock_id": lock_id,
        "patch_set_id": patch_set_id,
        "replacement_set_id": replacement_set_id,
        "lockfile_mode": lockfile_mode,
        "member_ids": member_ids,
    }


def run_binary(
    binary: Path,
    data_dir: Path,
    output: Path,
) -> tuple[int, dict[str, Any] | None, str, str]:
    output.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [str(binary), "--data-dir", str(data_dir), "--output", str(output)],
        capture_output=True,
        text=True,
        check=False,
    )
    data = None
    if output.is_file() and output.stat().st_size > 0:
        try:
            data = json.loads(output.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = None
    return proc.returncode, data, proc.stdout, proc.stderr


def run_expect_ok(binary: Path, data_dir: Path, output: Path) -> dict[str, Any]:
    rc, report, _out, err = run_binary(binary, data_dir, output)
    assert rc == 0, f"expected success, rc={rc} stderr={err}"
    assert report is not None, f"missing/invalid report output; stderr={err}"
    assert list(report.keys()) == TOP_LEVEL_KEYS
    return report


def run_expect_fatal(binary: Path, data_dir: Path, output: Path) -> tuple[int, str]:
    rc, report, _out, err = run_binary(binary, data_dir, output)
    assert rc != 0, "expected nonzero exit on fatal input"
    assert err.strip(), "expected nonempty stderr on fatal input"
    assert report is None
    assert not output.exists(), "fatal run must not leave an output file"
    assert not Path(str(output) + ".tmp").exists(), "fatal run must not leave a temp sibling"
    return rc, err


def copy_canon_fixture(dest: Path) -> Path:
    shutil.copytree(CANON_DATA, dest)
    return dest


def rows_for(report: dict[str, Any], key: str, request_id: str) -> list[dict[str, Any]]:
    return [r for r in report[key] if r["request_id"] == request_id]


def request_row_for(report: dict[str, Any], request_id: str) -> dict[str, Any]:
    matches = [r for r in report["request_rows"] if r["request_id"] == request_id]
    assert len(matches) == 1
    return matches[0]


def selection_by_name(report: dict[str, Any], request_id: str) -> dict[str, dict[str, Any]]:
    return {r["package_name"]: r for r in rows_for(report, "package_selection_rows", request_id)}


# ---------------------------------------------------------------------------
# Reference-assisted bootstrap: build a dataset where a request's *natural*
# resolution becomes a fully self-consistent previous lock, so a follow-up
# run should reuse every entry. This uses only the independent Python
# reference to derive digests/dependency sets for constructing inputs; it
# never substitutes for running the candidate binary.
# ---------------------------------------------------------------------------


def bootstrap_reusable_dataset(
    tmp_path: Path,
    name: str,
    *,
    resolver_mode: str,
    members: list[dict[str, Any]],
    registry: list[dict[str, Any]],
    patched: list[dict[str, Any]] | None = None,
    patch_set: dict[str, Any] | None = None,
    replacement_set: dict[str, Any] | None = None,
    lockfile_mode: str = "update",
) -> tuple[Path, str]:
    patch_set = patch_set or {"patch_set_id": "ps-empty", "patches": []}
    replacement_set = replacement_set or {
        "replacement_set_id": "rs-empty",
        "mappings": [],
        "replacement_records": [],
    }
    member_ids = [m["member_id"] for m in members]

    stage_dir = tmp_path / f"{name}_stage"
    dummy_lock = {
        "lock_id": "lock-dummy",
        "workspace_digest": "0" * 64,
        "patch_set_digest": "0" * 64,
        "replacement_set_digest": "0" * 64,
        "selected_packages": [],
    }
    staged_request = request_row(
        "req-main",
        member_ids,
        lock_id="lock-dummy",
        patch_set_id=patch_set["patch_set_id"],
        replacement_set_id=replacement_set["replacement_set_id"],
        lockfile_mode=lockfile_mode,
    )
    write_dataset(
        stage_dir,
        workspace_members=members,
        resolver_mode=resolver_mode,
        registry=registry,
        patched=patched,
        patch_sets=[patch_set],
        replacement_sets=[replacement_set],
        locks=[dummy_lock],
        requests=[staged_request],
    )
    ds = load_dataset(stage_dir)
    breq = ds.build_requests[0]
    result = process_request(ds, breq)
    assert result.status == "accepted", "bootstrap resolution must succeed to build a reusable lock"

    lock_packages = []
    for pkg_name, sel in sorted(result.selected.items()):
        dep_names = sorted({d.package_name for d in sel.candidate.dependencies})
        lock_packages.append(
            {
                "package_name": pkg_name,
                "version": sel.candidate.version,
                "source_kind": sel.selection_source,
                "source_reference": sel.source_reference,
                "source_digest": sel.source_digest,
                "checksum": sel.checksum,
                "dependency_names": dep_names,
            }
        )

    real_lock = {
        "lock_id": "lock-real",
        "workspace_digest": ds.workspace_digest,
        "patch_set_digest": ds.patch_digests[patch_set["patch_set_id"]],
        "replacement_set_digest": ds.replacement_digests[replacement_set["replacement_set_id"]],
        "selected_packages": lock_packages,
    }

    final_dir = tmp_path / f"{name}_data"
    final_request = request_row(
        "req-main",
        member_ids,
        lock_id="lock-real",
        patch_set_id=patch_set["patch_set_id"],
        replacement_set_id=replacement_set["replacement_set_id"],
        lockfile_mode=lockfile_mode,
    )
    write_dataset(
        final_dir,
        workspace_members=members,
        resolver_mode=resolver_mode,
        registry=registry,
        patched=patched,
        patch_sets=[patch_set],
        replacement_sets=[replacement_set],
        locks=[real_lock],
        requests=[final_request],
    )
    return final_dir, "req-main"


# ---------------------------------------------------------------------------
# test_01: CLI input schema and duplicate detection.
# ---------------------------------------------------------------------------


def test_01_cli_input_schema_and_duplicate_detection(binary: Path, tmp_path: Path) -> None:
    """Fatal structural problems exit nonzero with stderr and leave no output."""
    out = tmp_path / "out" / "report.json"

    # Missing required file.
    data_missing = copy_canon_fixture(tmp_path / "missing_file")
    (data_missing / "policy.json").unlink()
    run_expect_fatal(binary, data_missing, out)

    # Duplicate member_id within workspace.json.
    data_dup_member = copy_canon_fixture(tmp_path / "dup_member")
    ws = json.loads((data_dup_member / "workspace.json").read_text(encoding="utf-8"))
    dup = dict(ws["members"][0])
    ws["members"].append(dup)
    _write_json(data_dup_member / "workspace.json", ws)
    run_expect_fatal(binary, data_dup_member, tmp_path / "out2" / "report.json")

    # Malformed version string.
    data_bad_version = copy_canon_fixture(tmp_path / "bad_version")
    reg = json.loads((data_bad_version / "registry_packages.json").read_text(encoding="utf-8"))
    reg[0]["version"] = "1.2"
    _write_json(data_bad_version / "registry_packages.json", reg)
    run_expect_fatal(binary, data_bad_version, tmp_path / "out3" / "report.json")

    # Malformed sha-256 checksum.
    data_bad_sha = copy_canon_fixture(tmp_path / "bad_sha")
    reg2 = json.loads((data_bad_sha / "registry_packages.json").read_text(encoding="utf-8"))
    reg2[0]["checksum"] = "not-a-valid-checksum"
    _write_json(data_bad_sha / "registry_packages.json", reg2)
    run_expect_fatal(binary, data_bad_sha, tmp_path / "out4" / "report.json")

    # Duplicate request_id in build_requests.ndjson.
    data_dup_req = copy_canon_fixture(tmp_path / "dup_request")
    lines = (data_dup_req / "build_requests.ndjson").read_text(encoding="utf-8").splitlines()
    lines.append(lines[0])
    (data_dup_req / "build_requests.ndjson").write_text("\n".join(lines) + "\n", encoding="utf-8")
    run_expect_fatal(binary, data_dup_req, tmp_path / "out5" / "report.json")


# ---------------------------------------------------------------------------
# test_02: exact and caret requirement matching.
# ---------------------------------------------------------------------------


def test_02_exact_and_caret_requirement_matching(binary: Path, tmp_path: Path) -> None:
    """Exact `=` and all three caret upper-bound families match as specified."""
    # Unit-level checks against the independent reference parser.
    exact = Requirement.parse("=1.2.3")
    assert exact.matches(Version.parse("1.2.3"))
    assert not exact.matches(Version.parse("1.2.4"))

    big_caret = Requirement.parse("^1.4.2")
    assert not big_caret.matches(Version.parse("1.4.1"))
    assert big_caret.matches(Version.parse("1.4.2"))
    assert big_caret.matches(Version.parse("1.9.9"))
    assert not big_caret.matches(Version.parse("2.0.0"))

    mid_caret = Requirement.parse("^0.3.1")
    assert not mid_caret.matches(Version.parse("0.3.0"))
    assert mid_caret.matches(Version.parse("0.3.1"))
    assert mid_caret.matches(Version.parse("0.3.9"))
    assert not mid_caret.matches(Version.parse("0.4.0"))

    tiny_caret = Requirement.parse("^0.0.5")
    assert not tiny_caret.matches(Version.parse("0.0.4"))
    assert tiny_caret.matches(Version.parse("0.0.5"))
    assert not tiny_caret.matches(Version.parse("0.0.6"))

    # Binary-level confirmation: resolver_mode=allow isolates requirement
    # matching from MSRV preference, since allow always takes the numerically
    # greatest *valid* candidate.
    data_dir = tmp_path / "data"
    write_dataset(
        data_dir,
        resolver_mode="allow",
        workspace_members=[
            member(
                "mem-root",
                [
                    dep("capexact", "=1.2.3"),
                    dep("captiny", "^0.0.5"),
                    dep("capmid", "^0.3.0"),
                    dep("capbig", "^2.0.0"),
                ],
            )
        ],
        registry=[
            reg_pkg("capexact", "1.2.2"),
            reg_pkg("capexact", "1.2.3"),
            reg_pkg("capexact", "1.2.4"),
            reg_pkg("captiny", "0.0.4"),
            reg_pkg("captiny", "0.0.5"),
            reg_pkg("captiny", "0.0.6"),
            reg_pkg("capmid", "0.2.9"),
            reg_pkg("capmid", "0.3.0"),
            reg_pkg("capmid", "0.3.5"),
            reg_pkg("capmid", "0.4.0"),
            reg_pkg("capbig", "1.9.9"),
            reg_pkg("capbig", "2.0.0"),
            reg_pkg("capbig", "2.5.0"),
            reg_pkg("capbig", "3.0.0"),
        ],
        requests=[request_row("req-caret", ["mem-root"])],
    )
    report = run_expect_ok(binary, data_dir, tmp_path / "out" / "report.json")
    sel = selection_by_name(report, "req-caret")
    assert sel["capexact"]["selected_version"] == "1.2.3"
    assert sel["captiny"]["selected_version"] == "0.0.5"
    assert sel["capmid"]["selected_version"] == "0.3.5"
    assert sel["capbig"]["selected_version"] == "2.5.0"


# ---------------------------------------------------------------------------
# test_03: root member dependency seeding.
# ---------------------------------------------------------------------------


def test_03_root_member_dependency_seeding(binary: Path, tmp_path: Path) -> None:
    """Only requested members seed active requirements for a request."""
    data_dir = copy_canon_fixture(tmp_path / "data")
    requests = [
        request_row(
            "req-transport-only",
            ["mem-transport"],
            lock_id="lock-baseline",
            replacement_set_id="rs-equiv",
        )
    ]
    _write_ndjson(data_dir / "build_requests.ndjson", requests)

    report = run_expect_ok(binary, data_dir, tmp_path / "out" / "report.json")
    sel = selection_by_name(report, "req-transport-only")
    # mem-transport depends only on codec (which pulls in helper); mem-app's
    # utility/logger must never be seeded.
    assert set(sel.keys()) == {"codec", "helper"}


# ---------------------------------------------------------------------------
# test_04: transitive resolution fixed point.
# ---------------------------------------------------------------------------


def test_04_transitive_resolution_fixed_point(binary: Path, tmp_path: Path) -> None:
    """A transitive dependency introduced mid-resolution can tighten and
    change an already-selected package's version."""
    data_dir = tmp_path / "data"
    write_dataset(
        data_dir,
        resolver_mode="allow",
        workspace_members=[member("mem-root", [dep("top", "^1.0.0"), dep("shared", "^1.0.0")])],
        registry=[
            reg_pkg("top", "1.0.0", dependencies=[dep("shared", "=1.2.0")]),
            reg_pkg("shared", "1.0.0"),
            reg_pkg("shared", "1.2.0"),
            reg_pkg("shared", "1.5.0"),
        ],
        requests=[request_row("req-fixed-point", ["mem-root"])],
    )
    report = run_expect_ok(binary, data_dir, tmp_path / "out" / "report.json")
    sel = selection_by_name(report, "req-fixed-point")
    # A naive single-pass resolver picks the direct-requirement greatest
    # (1.5.0); only fixed-point iteration re-tightens shared to 1.2.0 once
    # top's transitive exact requirement is loaded.
    assert sel["shared"]["selected_version"] == "1.2.0"
    assert sel["top"]["selected_version"] == "1.0.0"


# ---------------------------------------------------------------------------
# test_05: resolution independent of registry order.
# ---------------------------------------------------------------------------


def test_05_resolution_independent_of_registry_order(binary: Path, tmp_path: Path) -> None:
    """Shuffling registry_packages.json must not change the candidate's own
    selections for identical requests (self-comparison, not vs. reference)."""
    data_a = copy_canon_fixture(tmp_path / "data_a")
    report_a = run_expect_ok(binary, data_a, tmp_path / "out_a" / "report.json")

    data_b = copy_canon_fixture(tmp_path / "data_b")
    reg = json.loads((data_b / "registry_packages.json").read_text(encoding="utf-8"))
    rng = random.Random(20260724)
    shuffled = list(reg)
    rng.shuffle(shuffled)
    _write_json(data_b / "registry_packages.json", shuffled)
    report_b = run_expect_ok(binary, data_b, tmp_path / "out_b" / "report.json")

    assert report_a["package_selection_rows"] == report_b["package_selection_rows"]
    assert report_a["request_rows"] == report_b["request_rows"]


# ---------------------------------------------------------------------------
# test_06: existing lock preference over a newer registry candidate.
# ---------------------------------------------------------------------------


def test_06_existing_lock_preference(binary: Path, tmp_path: Path) -> None:
    """A still-valid locked version is preferred even when fallback/allow
    would otherwise pick a numerically greater candidate."""
    data_dir = tmp_path / "data"
    lock = {
        "lock_id": "lock-pref",
        "workspace_digest": "0" * 64,
        "patch_set_digest": "0" * 64,
        "replacement_set_digest": "0" * 64,
        "selected_packages": [
            {
                "package_name": "pkgl",
                "version": "1.1.0",
                "source_kind": "registry",
                "source_reference": "crates-io",
                "source_digest": digest_of(
                    {
                        "checksum": sha256_hex("crates-io:pkgl:1.1.0"),
                        "package_name": "pkgl",
                        "source_id": "crates-io",
                        "version": "1.1.0",
                    }
                ),
                "checksum": sha256_hex("crates-io:pkgl:1.1.0"),
                "dependency_names": [],
            }
        ],
    }
    write_dataset(
        data_dir,
        resolver_mode="fallback",
        workspace_members=[member("mem-root", [dep("pkgl", "^1.0.0")], rust_version="1.90.0")],
        registry=[reg_pkg("pkgl", "1.0.0"), reg_pkg("pkgl", "1.1.0"), reg_pkg("pkgl", "1.2.0")],
        locks=[lock],
        requests=[request_row("req-lock-pref", ["mem-root"], lock_id="lock-pref")],
    )
    report = run_expect_ok(binary, data_dir, tmp_path / "out" / "report.json")
    sel = selection_by_name(report, "req-lock-pref")
    assert sel["pkgl"]["selected_version"] == "1.1.0"
    assert sel["pkgl"]["locked_version_or_null"] == "1.1.0"


# ---------------------------------------------------------------------------
# test_07: locked-yanked eligibility vs unlocked-yanked exclusion.
# ---------------------------------------------------------------------------


def test_07_locked_and_unlocked_yanked_behavior(binary: Path, tmp_path: Path) -> None:
    """A yanked version stays eligible only when reused from the selected
    prior lock; without that lock entry it is always excluded."""
    registry = [reg_pkg("yp", "1.0.0", yanked=False), reg_pkg("yp", "1.1.0", yanked=True)]
    members = [member("mem-root", [dep("yp", "^1.0.0")])]

    data_locked = tmp_path / "locked"
    lock = {
        "lock_id": "lock-yp",
        "workspace_digest": "0" * 64,
        "patch_set_digest": "0" * 64,
        "replacement_set_digest": "0" * 64,
        "selected_packages": [
            {
                "package_name": "yp",
                "version": "1.1.0",
                "source_kind": "registry",
                "source_reference": "crates-io",
                "source_digest": digest_of(
                    {
                        "checksum": sha256_hex("crates-io:yp:1.1.0"),
                        "package_name": "yp",
                        "source_id": "crates-io",
                        "version": "1.1.0",
                    }
                ),
                "checksum": sha256_hex("crates-io:yp:1.1.0"),
                "dependency_names": [],
            }
        ],
    }
    write_dataset(
        data_locked,
        workspace_members=members,
        registry=registry,
        locks=[lock],
        requests=[request_row("req-locked-yank", ["mem-root"], lock_id="lock-yp")],
    )
    report_locked = run_expect_ok(binary, data_locked, tmp_path / "out_locked" / "report.json")
    sel_locked = selection_by_name(report_locked, "req-locked-yank")
    assert sel_locked["yp"]["selected_version"] == "1.1.0"
    assert sel_locked["yp"]["yanked"] is True

    data_unlocked = tmp_path / "unlocked"
    write_dataset(
        data_unlocked,
        workspace_members=members,
        registry=registry,
        requests=[request_row("req-unlocked-yank", ["mem-root"], lock_id="lock-empty")],
    )
    out_unlocked = tmp_path / "out_unlocked" / "report.json"
    report_unlocked = run_expect_ok(binary, data_unlocked, out_unlocked)
    sel_unlocked = selection_by_name(report_unlocked, "req-unlocked-yank")
    assert sel_unlocked["yp"]["selected_version"] == "1.0.0"
    assert sel_unlocked["yp"]["yanked"] is False


# ---------------------------------------------------------------------------
# test_08 / test_09: root-only patch overlay.
# ---------------------------------------------------------------------------


def test_08_root_patch_overlay_selection(binary: Path, tmp_path: Path) -> None:
    """The selected root patch set overlays its declared source and can win
    resolution; an unselected valid patch is projected as unused."""
    data_dir = copy_canon_fixture(tmp_path / "data")
    patched = json.loads((data_dir / "patched_packages.json").read_text(encoding="utf-8"))
    codec_patch = next(p for p in patched if p["patched_package_id"] == "pp-codec-120")

    report = run_expect_ok(binary, data_dir, tmp_path / "out" / "report.json")
    sel = selection_by_name(report, "req-patch-update")
    assert sel["codec"]["selected_version"] == "1.2.0"
    assert sel["codec"]["selection_source"] == "patched_path"
    assert sel["codec"]["source_reference"] == codec_patch["source_reference"]
    assert sel["codec"]["source_digest"] == codec_patch["source_digest"]

    patch_rows = rows_for(report, "patch_rows", "req-patch-update")
    codec_row = next(r for r in patch_rows if r["package_name"] == "codec")
    assert codec_row["status"] == "selected"
    assert codec_row["reason_or_null"] is None


def test_09_patch_replacement_and_unused_projection(binary: Path, tmp_path: Path) -> None:
    """A same-version patch fully replaces the registry candidate, and a
    structurally valid patch that loses resolution is projected as unused."""
    data_dir = tmp_path / "data"
    patched_pkg = {
        "patched_package_id": "pp-q-100",
        "package_name": "pkgq",
        "version": "1.0.0",
        "patched_source_id": "crates-io",
        "source_kind": "path_snapshot",
        "source_reference": "path+file:///vendor/pkgq-1.0.0-patch",
        "source_digest": sha256_hex("patched-pkgq-1.0.0"),
        "rust_version": "1.0.0",
        "dependencies": [],
    }
    unused_patched_pkg = {
        "patched_package_id": "pp-r-500",
        "package_name": "pkgr",
        "version": "5.0.0",
        "patched_source_id": "crates-io",
        "source_kind": "path_snapshot",
        "source_reference": "path+file:///vendor/pkgr-5.0.0-patch",
        "source_digest": sha256_hex("patched-pkgr-5.0.0"),
        "rust_version": "1.0.0",
        "dependencies": [],
    }
    patch_set = {
        "patch_set_id": "ps-mixed",
        "patches": [
            {"source_id": "crates-io", "package_name": "pkgq", "patched_package_id": "pp-q-100"},
            {"source_id": "crates-io", "package_name": "pkgr", "patched_package_id": "pp-r-500"},
        ],
    }
    write_dataset(
        data_dir,
        workspace_members=[member("mem-root", [dep("pkgq", "^1.0.0"), dep("pkgr", "=1.0.0")])],
        registry=[
            reg_pkg("pkgq", "1.0.0"),
            reg_pkg("pkgq", "2.0.0"),
            reg_pkg("pkgr", "1.0.0"),
            reg_pkg("pkgr", "5.0.0"),
        ],
        patched=[patched_pkg, unused_patched_pkg],
        patch_sets=[patch_set],
        requests=[request_row("req-mixed-patch", ["mem-root"], patch_set_id="ps-mixed")],
    )
    report = run_expect_ok(binary, data_dir, tmp_path / "out" / "report.json")
    sel = selection_by_name(report, "req-mixed-patch")
    # pkgq's only valid candidate at version 1.0.0 is now entirely the
    # patched record (same-version replacement of the registry entry).
    assert sel["pkgq"]["selected_version"] == "1.0.0"
    assert sel["pkgq"]["selection_source"] == "patched_path"
    assert sel["pkgq"]["source_digest"] == patched_pkg["source_digest"]
    # pkgr's exact requirement (=1.0.0) can never select the patched 5.0.0
    # candidate, so it is a structurally valid but unused patch.
    assert sel["pkgr"]["selected_version"] == "1.0.0"
    assert sel["pkgr"]["selection_source"] == "registry"

    patch_rows = rows_for(report, "patch_rows", "req-mixed-patch")
    by_pkg = {r["package_name"]: r for r in patch_rows}
    assert by_pkg["pkgq"]["status"] == "selected"
    assert by_pkg["pkgr"]["status"] == "unused"
    assert by_pkg["pkgr"]["reason_or_null"] is None


# ---------------------------------------------------------------------------
# test_10: patch conflict.
# ---------------------------------------------------------------------------


def test_10_patch_conflict(binary: Path, tmp_path: Path) -> None:
    """Two patch entries targeting the same (source_id, package_name,
    version) are a patch_conflict and reject the request."""
    data_dir = tmp_path / "data"
    patched = [
        {
            "patched_package_id": "pp-dup-a",
            "package_name": "pkgd",
            "version": "1.0.0",
            "patched_source_id": "crates-io",
            "source_kind": "path_snapshot",
            "source_reference": "path+file:///vendor/pkgd-a",
            "source_digest": sha256_hex("patched-pkgd-a"),
            "rust_version": "1.0.0",
            "dependencies": [],
        },
        {
            "patched_package_id": "pp-dup-b",
            "package_name": "pkgd",
            "version": "1.0.0",
            "patched_source_id": "crates-io",
            "source_kind": "git_snapshot",
            "source_reference": "git+https://example.invalid/pkgd?rev=z",
            "source_digest": sha256_hex("patched-pkgd-b"),
            "rust_version": "1.0.0",
            "dependencies": [],
        },
    ]
    patch_set = {
        "patch_set_id": "ps-conflict",
        "patches": [
            {"source_id": "crates-io", "package_name": "pkgd", "patched_package_id": "pp-dup-a"},
            {"source_id": "crates-io", "package_name": "pkgd", "patched_package_id": "pp-dup-b"},
        ],
    }
    write_dataset(
        data_dir,
        workspace_members=[member("mem-root", [dep("pkgd", "^1.0.0")])],
        registry=[reg_pkg("pkgd", "1.0.0")],
        patched=patched,
        patch_sets=[patch_set],
        requests=[request_row("req-conflict", ["mem-root"], patch_set_id="ps-conflict")],
    )
    report = run_expect_ok(binary, data_dir, tmp_path / "out" / "report.json")
    row = request_row_for(report, "req-conflict")
    assert row["status"] == "rejected"
    assert row["reason_or_null"] == "patch_conflict"
    conflicts = rows_for(report, "conflict_rows", "req-conflict")
    assert any(c["reason_code"] == "patch_conflict" for c in conflicts)


# ---------------------------------------------------------------------------
# test_11 / test_12: equivalent source replacement.
# ---------------------------------------------------------------------------


def test_11_source_replacement_equivalence(binary: Path, tmp_path: Path) -> None:
    """A replacement source with an identical checksum projects `equivalent`
    and rewrites the reported source without changing the selected version."""
    data_dir = copy_canon_fixture(tmp_path / "data")
    report = run_expect_ok(binary, data_dir, tmp_path / "out" / "report.json")

    replacement_rows = rows_for(report, "source_replacement_rows", "req-yanked-reuse")
    assert replacement_rows, "expected replacement rows for req-yanked-reuse"
    for row in replacement_rows:
        assert row["status"] == "equivalent"
        assert row["replacement_checksum_or_null"] == row["original_checksum"]

    sel = selection_by_name(report, "req-yanked-reuse")
    for row in sel.values():
        assert row["selection_source"] == "replacement_registry"


def test_12_source_replacement_missing_or_mismatch(binary: Path, tmp_path: Path) -> None:
    """A checksum mismatch or a missing replacement record rejects the
    request with the matching reason code."""
    # Mismatch: canonical fixture's rs-mismatch has a wrong checksum for the
    # selected codec 1.1.0 record.
    data_mismatch = copy_canon_fixture(tmp_path / "mismatch")
    out_mismatch = tmp_path / "out_mismatch" / "report.json"
    report_mismatch = run_expect_ok(binary, data_mismatch, out_mismatch)
    row = request_row_for(report_mismatch, "req-replace-bad")
    assert row["status"] == "rejected"
    assert row["reason_or_null"] == "source_replacement_mismatch"

    # Missing: drop the logger 1.0.0 replacement record entirely, which the
    # req-yanked-reuse resolution selects.
    data_missing = copy_canon_fixture(tmp_path / "missing")
    rs = json.loads((data_missing / "replacement_sources.json").read_text(encoding="utf-8"))
    for entry in rs:
        if entry["replacement_set_id"] == "rs-equiv":
            entry["replacement_records"] = [
                r
                for r in entry["replacement_records"]
                if not (r["package_name"] == "logger" and r["version"] == "1.0.0")
            ]
    _write_json(data_missing / "replacement_sources.json", rs)
    report_missing = run_expect_ok(binary, data_missing, tmp_path / "out_missing" / "report.json")
    row2 = request_row_for(report_missing, "req-yanked-reuse")
    assert row2["status"] == "rejected"
    assert row2["reason_or_null"] == "source_replacement_missing"


# ---------------------------------------------------------------------------
# test_13 / test_14 / test_15: MSRV allow/fallback preference.
# ---------------------------------------------------------------------------


def _msrv_registry() -> list[dict[str, Any]]:
    return [
        reg_pkg("helper", "1.0.0", rust_version="1.55.0"),
        reg_pkg("helper", "1.1.0", rust_version="1.65.0"),
        reg_pkg("helper", "1.2.0", rust_version="1.90.0"),
    ]


def test_13_msrv_allow_mode(binary: Path, tmp_path: Path) -> None:
    """`allow` mode selects the numerically greatest candidate regardless of
    Rust-version compatibility."""
    data_dir = tmp_path / "data"
    write_dataset(
        data_dir,
        resolver_mode="allow",
        workspace_members=[member("mem-root", [dep("helper", "^1.0.0")], rust_version="1.70.0")],
        registry=_msrv_registry(),
        requests=[request_row("req-allow", ["mem-root"])],
    )
    report = run_expect_ok(binary, data_dir, tmp_path / "out" / "report.json")
    sel = selection_by_name(report, "req-allow")
    assert sel["helper"]["selected_version"] == "1.2.0"
    assert sel["helper"]["msrv_compatible"] is False


def test_14_msrv_fallback_compatible_preference(binary: Path, tmp_path: Path) -> None:
    """`fallback` mode prefers the numerically greatest MSRV-compatible
    candidate over an incompatible greater one."""
    data_dir = tmp_path / "data"
    write_dataset(
        data_dir,
        resolver_mode="fallback",
        workspace_members=[member("mem-root", [dep("helper", "^1.0.0")], rust_version="1.70.0")],
        registry=_msrv_registry(),
        requests=[request_row("req-fallback", ["mem-root"])],
    )
    report = run_expect_ok(binary, data_dir, tmp_path / "out" / "report.json")
    sel = selection_by_name(report, "req-fallback")
    assert sel["helper"]["selected_version"] == "1.1.0"
    assert sel["helper"]["msrv_compatible"] is True


def test_15_msrv_fallback_incompatible_last_resort(binary: Path, tmp_path: Path) -> None:
    """When no MSRV-compatible candidate matches, `fallback` selects the
    numerically greatest incompatible candidate instead of rejecting."""
    data_dir = tmp_path / "data"
    write_dataset(
        data_dir,
        resolver_mode="fallback",
        workspace_members=[member("mem-root", [dep("helper", "^1.0.0")], rust_version="1.70.0")],
        registry=[
            reg_pkg("helper", "1.8.0", rust_version="1.90.0"),
            reg_pkg("helper", "1.9.0", rust_version="1.95.0"),
        ],
        requests=[request_row("req-last-resort", ["mem-root"])],
    )
    report = run_expect_ok(binary, data_dir, tmp_path / "out" / "report.json")
    sel = selection_by_name(report, "req-last-resort")
    assert sel["helper"]["selected_version"] == "1.9.0"
    assert sel["helper"]["msrv_compatible"] is False


# ---------------------------------------------------------------------------
# test_16: requirement conflict and resolution round limit.
# ---------------------------------------------------------------------------


def test_16_requirement_conflict_and_round_limit(binary: Path, tmp_path: Path) -> None:
    """An empty requirement intersection rejects with package_version_conflict;
    an exhausted round budget rejects with resolution_round_limit."""
    data_conflict = tmp_path / "conflict"
    write_dataset(
        data_conflict,
        workspace_members=[
            member("mem-a", [dep("shared", "=1.0.0")]),
            member("mem-b", [dep("shared", "=2.0.0")]),
        ],
        registry=[reg_pkg("shared", "1.0.0"), reg_pkg("shared", "2.0.0")],
        requests=[request_row("req-conflict", ["mem-a", "mem-b"])],
    )
    out_conflict = tmp_path / "out_conflict" / "report.json"
    report_conflict = run_expect_ok(binary, data_conflict, out_conflict)
    row = request_row_for(report_conflict, "req-conflict")
    assert row["status"] == "rejected"
    assert row["reason_or_null"] == "package_version_conflict"

    # maximum_resolution_rounds=1 leaves no round to confirm a fixed point,
    # so even a single trivial selection cannot converge.
    data_round_limit = tmp_path / "round_limit"
    write_dataset(
        data_round_limit,
        workspace_members=[member("mem-root", [dep("pkgz", "^1.0.0")])],
        registry=[reg_pkg("pkgz", "1.0.0")],
        requests=[request_row("req-round-limit", ["mem-root"])],
        policy={**DEFAULT_POLICY, "maximum_resolution_rounds": 1},
    )
    out_round = tmp_path / "out_round" / "report.json"
    report_round_limit = run_expect_ok(binary, data_round_limit, out_round)
    row2 = request_row_for(report_round_limit, "req-round-limit")
    assert row2["status"] == "rejected"
    assert row2["reason_or_null"] == "resolution_round_limit"


# ---------------------------------------------------------------------------
# test_17: complete lock reuse.
# ---------------------------------------------------------------------------


def test_17_complete_lock_reuse(binary: Path, tmp_path: Path) -> None:
    """req-yanked-reuse reuses every selected lock entry unchanged."""
    data_dir = copy_canon_fixture(tmp_path / "data")
    report = run_expect_ok(binary, data_dir, tmp_path / "out" / "report.json")

    req_row = request_row_for(report, "req-yanked-reuse")
    assert req_row["status"] == "accepted"
    assert req_row["recomputed_lock_entry_count"] == 0
    assert req_row["reused_lock_entry_count"] == req_row["selected_package_count"]

    sel = selection_by_name(report, "req-yanked-reuse")
    assert sel, "expected package selections for req-yanked-reuse"
    for row in sel.values():
        assert row["lock_status"] == "reused"

    lock_rows = rows_for(report, "lock_entry_rows", "req-yanked-reuse")
    assert lock_rows
    for row in lock_rows:
        assert row["status"] == "reused"
        assert row["prior_digest_or_null"] == row["computed_digest"]

    assert not rows_for(report, "invalidation_rows", "req-yanked-reuse")


# ---------------------------------------------------------------------------
# test_18: selected source digest invalidation.
# ---------------------------------------------------------------------------


def test_18_selected_source_digest_invalidation(binary: Path, tmp_path: Path) -> None:
    """Mutating a selected package's source so its digest changes invalidates
    that package (and its reverse dependents), even though it is still
    selected and still satisfies its requirement."""
    members = [member("mem-root", [dep("pkgt", "^1.0.0")])]
    registry = [
        reg_pkg("pkgt", "1.0.0", dependencies=[dep("pkgs", "^1.0.0")]),
        reg_pkg("pkgs", "1.0.0"),
    ]
    data_dir, request_id = bootstrap_reusable_dataset(
        tmp_path,
        "digest_invalidation",
        resolver_mode="fallback",
        members=members,
        registry=registry,
    )
    baseline = run_expect_ok(binary, data_dir, tmp_path / "out_baseline" / "report.json")
    sel_baseline = selection_by_name(baseline, request_id)
    assert sel_baseline["pkgt"]["lock_status"] == "reused"
    assert sel_baseline["pkgs"]["lock_status"] == "reused"

    reg = json.loads((data_dir / "registry_packages.json").read_text(encoding="utf-8"))
    for entry in reg:
        if entry["package_name"] == "pkgs":
            entry["checksum"] = sha256_hex("mutated-pkgs-1.0.0-checksum")
    _write_json(data_dir / "registry_packages.json", reg)

    mutated = run_expect_ok(binary, data_dir, tmp_path / "out_mutated" / "report.json")
    sel_mutated = selection_by_name(mutated, request_id)
    assert sel_mutated["pkgs"]["lock_status"] == "recomputed"
    assert sel_mutated["pkgt"]["lock_status"] == "recomputed"

    invalidation_rows = rows_for(mutated, "invalidation_rows", request_id)
    invalidations = {r["package_name"]: r for r in invalidation_rows}
    assert invalidations["pkgs"]["cause_kind"] == "source_changed"
    assert invalidations["pkgt"]["cause_kind"] == "upstream_invalidated"
    assert invalidations["pkgt"]["cause_subject"] == "pkgs"


# ---------------------------------------------------------------------------
# test_19: unselected registry mutation locality.
# ---------------------------------------------------------------------------


def test_19_unselected_registry_mutation_locality(binary: Path, tmp_path: Path) -> None:
    """Mutating a registry package that is never selected must not disturb
    unrelated lock entries."""
    data_dir = copy_canon_fixture(tmp_path / "data")
    reg = json.loads((data_dir / "registry_packages.json").read_text(encoding="utf-8"))
    mutated_any = False
    for entry in reg:
        if entry["package_name"] == "syncutil":
            entry["checksum"] = sha256_hex("mutated-syncutil-checksum")
            entry["rust_version"] = "1.99.0"
            mutated_any = True
    assert mutated_any, "expected syncutil in the canonical registry fixture"
    _write_json(data_dir / "registry_packages.json", reg)

    report = run_expect_ok(binary, data_dir, tmp_path / "out" / "report.json")
    sel = selection_by_name(report, "req-yanked-reuse")
    for row in sel.values():
        assert row["lock_status"] == "reused"
    assert not rows_for(report, "invalidation_rows", "req-yanked-reuse")


# ---------------------------------------------------------------------------
# test_20: frozen-mode stale lock rejection.
# ---------------------------------------------------------------------------


def test_20_frozen_mode_stale_lock_rejection(binary: Path, tmp_path: Path) -> None:
    """`frozen` mode rejects with lockfile_stale instead of recomputing, and
    emits no package/lock/invalidation/replacement detail rows for it."""
    data_dir = copy_canon_fixture(tmp_path / "data")
    report = run_expect_ok(binary, data_dir, tmp_path / "out" / "report.json")

    row = request_row_for(report, "req-patch-frozen")
    assert row["status"] == "rejected"
    assert row["reason_or_null"] == "lockfile_stale"
    assert row["selected_package_count"] == 0

    assert not rows_for(report, "package_selection_rows", "req-patch-frozen")
    assert not rows_for(report, "lock_entry_rows", "req-patch-frozen")
    assert not rows_for(report, "invalidation_rows", "req-patch-frozen")
    assert not rows_for(report, "source_replacement_rows", "req-patch-frozen")

    conflicts = rows_for(report, "conflict_rows", "req-patch-frozen")
    assert any(c["reason_code"] == "lockfile_stale" for c in conflicts)


# ---------------------------------------------------------------------------
# test_21: dynamic patch/MSRV mutation locality.
# ---------------------------------------------------------------------------


def test_21_dynamic_patch_or_msrv_mutation_locality(binary: Path, tmp_path: Path) -> None:
    """A single runtime mutation only changes the rows of packages affected
    by it; unrelated packages in the same request stay reused."""
    members = [member("mem-root", [dep("pkgc", "^1.0.0"), dep("pkgd", "^1.0.0")])]
    registry = [
        reg_pkg("pkgc", "1.0.0", dependencies=[dep("pkgb", "^1.0.0")]),
        reg_pkg("pkgb", "1.0.0", dependencies=[dep("pkga", "^1.0.0")]),
        reg_pkg("pkga", "1.0.0"),
        reg_pkg("pkgd", "1.0.0"),
    ]
    data_dir, request_id = bootstrap_reusable_dataset(
        tmp_path, "mutation_locality", resolver_mode="fallback", members=members, registry=registry
    )
    baseline = run_expect_ok(binary, data_dir, tmp_path / "out_baseline" / "report.json")
    sel_baseline = selection_by_name(baseline, request_id)
    for name in ("pkga", "pkgb", "pkgc", "pkgd"):
        assert sel_baseline[name]["lock_status"] == "reused"

    reg = json.loads((data_dir / "registry_packages.json").read_text(encoding="utf-8"))
    for entry in reg:
        if entry["package_name"] == "pkgb":
            entry["checksum"] = sha256_hex("mutated-pkgb-checksum")
    _write_json(data_dir / "registry_packages.json", reg)

    mutated = run_expect_ok(binary, data_dir, tmp_path / "out_mutated" / "report.json")
    sel_mutated = selection_by_name(mutated, request_id)
    assert sel_mutated["pkgb"]["lock_status"] == "recomputed"
    assert sel_mutated["pkgc"]["lock_status"] == "recomputed"
    # pkga has no dependency on pkgb; pkgd is entirely unrelated. Locality
    # requires both to remain reused.
    assert sel_mutated["pkga"]["lock_status"] == "reused"
    assert sel_mutated["pkgd"]["lock_status"] == "reused"


# ---------------------------------------------------------------------------
# test_22: five-seed input permutation invariance.
# ---------------------------------------------------------------------------


def _shuffle_unordered(data_dir: Path, seed: int) -> None:
    rng = random.Random(seed)

    reg = json.loads((data_dir / "registry_packages.json").read_text(encoding="utf-8"))
    rng.shuffle(reg)
    for entry in reg:
        rng.shuffle(entry["dependencies"])
    _write_json(data_dir / "registry_packages.json", reg)

    ws = json.loads((data_dir / "workspace.json").read_text(encoding="utf-8"))
    rng.shuffle(ws["members"])
    for m in ws["members"]:
        rng.shuffle(m["dependencies"])
    _write_json(data_dir / "workspace.json", ws)

    patched = json.loads((data_dir / "patched_packages.json").read_text(encoding="utf-8"))
    rng.shuffle(patched)
    _write_json(data_dir / "patched_packages.json", patched)

    patch_sets = json.loads((data_dir / "patch_sets.json").read_text(encoding="utf-8"))
    for ps in patch_sets:
        rng.shuffle(ps["patches"])
    rng.shuffle(patch_sets)
    _write_json(data_dir / "patch_sets.json", patch_sets)

    repl = json.loads((data_dir / "replacement_sources.json").read_text(encoding="utf-8"))
    for rs in repl:
        rng.shuffle(rs["mappings"])
        rng.shuffle(rs["replacement_records"])
    rng.shuffle(repl)
    _write_json(data_dir / "replacement_sources.json", repl)

    locks = json.loads((data_dir / "previous_locks.json").read_text(encoding="utf-8"))
    for lk in locks:
        rng.shuffle(lk["selected_packages"])
        for pkg in lk["selected_packages"]:
            rng.shuffle(pkg["dependency_names"])
    rng.shuffle(locks)
    _write_json(data_dir / "previous_locks.json", locks)

    lines = (data_dir / "build_requests.ndjson").read_text(encoding="utf-8").splitlines()
    req_dicts = [json.loads(line) for line in lines if line.strip()]
    for r in req_dicts:
        rng.shuffle(r["member_ids"])
    rng.shuffle(req_dicts)
    _write_ndjson(data_dir / "build_requests.ndjson", req_dicts)


def test_22_five_seed_input_permutation_invariance(binary: Path, tmp_path: Path) -> None:
    """Shuffling every unordered array/record across five seeds must not
    change the candidate's own selections (self-comparison per seed)."""
    baseline_dir = copy_canon_fixture(tmp_path / "baseline")
    baseline = run_expect_ok(binary, baseline_dir, tmp_path / "out_baseline" / "report.json")

    for seed in (7, 19, 41, 83, 127):
        seeded_dir = copy_canon_fixture(tmp_path / f"seed_{seed}")
        _shuffle_unordered(seeded_dir, seed)
        report = run_expect_ok(binary, seeded_dir, tmp_path / f"out_seed_{seed}" / "report.json")
        assert report["package_selection_rows"] == baseline["package_selection_rows"], seed
        assert report["request_rows"] == baseline["request_rows"], seed
        assert report["summary"] == baseline["summary"], seed


# ---------------------------------------------------------------------------
# test_24: byte-identical rerun, malformed input, stale-output cleanup.
# ---------------------------------------------------------------------------


def test_24_byte_identical_rerun_malformed_input_and_stale_cleanup(
    binary: Path, tmp_path: Path
) -> None:
    """Re-running against unchanged input yields byte-identical canonical
    output; malformed JSON is fatal; and any stale output (plus its temp
    sibling) is removed before a failing run exits."""
    data_dir = copy_canon_fixture(tmp_path / "data")
    output = tmp_path / "out" / "report.json"
    rc1, report1, _out1, err1 = run_binary(binary, data_dir, output)
    assert rc1 == 0 and report1 is not None, err1
    first_bytes = output.read_bytes()

    rc2, report2, _out2, err2 = run_binary(binary, data_dir, output)
    assert rc2 == 0 and report2 is not None, err2
    second_bytes = output.read_bytes()
    assert first_bytes == second_bytes, "identical input must yield byte-identical output"

    # Malformed JSON is a whole-run fatal condition.
    data_broken = copy_canon_fixture(tmp_path / "broken")
    (data_broken / "workspace.json").write_text("{not valid json", encoding="utf-8")

    stale_output = tmp_path / "stale" / "report.json"
    stale_output.parent.mkdir(parents=True, exist_ok=True)
    stale_output.write_text("stale-report-contents", encoding="utf-8")
    stale_tmp = Path(str(stale_output) + ".tmp")
    stale_tmp.write_text("stale-tmp-contents", encoding="utf-8")

    rc3, report3, _out3, err3 = run_binary(binary, data_broken, stale_output)
    assert rc3 != 0
    assert report3 is None
    assert err3.strip()
    assert not stale_output.exists(), "stale output must be removed on fatal failure"
    assert not stale_tmp.exists(), "stale temp sibling must be removed on fatal failure"
