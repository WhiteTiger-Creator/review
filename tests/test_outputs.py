"""Behavioral verifier for audit-java-duckdb-trivia-dungeon.

Invokes /app/bin/trivia-dungeon and the bundled Makefile verify target.
Compares issue tuples (artifact, pointer, code) rather than validator message text.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
from pathlib import Path

import pytest

from helpers import case_factory
from helpers.report_assertions import (
    assert_audit_success,
    assert_canonical_json_bytes,
    assert_immutable_hashes,
    assert_issue_sets_equal,
    assert_no_completed_audit_on_operational_failure,
    assert_playthrough_matches_schema_dir,
    assert_posix_relative_artifacts,
    assert_report_matches_schema_dir,
    issue_tuples,
    load_fixture_hashes,
    load_json,
)
from helpers.expectation_model import (
    canonical_rows,
    dataset_digest,
    question_fingerprint,
)
from helpers.subprocess_utils import (
    APP_ROOT,
    CONTRACTS,
    DATASET,
    DEFAULT_OUTPUT,
    EXIT_CONTENT,
    EXIT_OPERATIONAL,
    EXIT_SUCCESS,
    audit_report_path,
    clear_directory,
    playthrough_report_path,
    run_trivia_dungeon,
)

FIXTURE_HASHES = Path(__file__).resolve().parent / "fixture_hashes.json"
BUNDLED_CONFIG = APP_ROOT / "config" / "dungeon.toml"
BUNDLED_ANSWERS = APP_ROOT / "config" / "verification-answers.toml"


@pytest.fixture(scope="session", autouse=True)
def _ensure_app_built_once() -> None:
    """Prebuild the shaded jar once; the image already ships a built artifact."""
    from helpers.subprocess_utils import ensure_built

    ensure_built()


@pytest.fixture(scope="session")
def fixture_hashes() -> dict[str, str]:
    return load_fixture_hashes(FIXTURE_HASHES)


def _read_report(path: Path) -> dict:
    return load_json(path)


def _run_audit(case: case_factory.DungeonCase, *, cwd: Path | None = None, env: dict | None = None):
    case.output.mkdir(parents=True, exist_ok=True)
    case.state.parent.mkdir(parents=True, exist_ok=True)
    return run_trivia_dungeon(
        "audit",
        root=case.root,
        config=case.config,
        dataset=case.dataset,
        contracts=case.contracts,
        output=case.output,
        state=case.state,
        cwd=cwd or case.root,
        env=env,
    )


def _run_playthrough(case: case_factory.DungeonCase, *, cwd: Path | None = None, env: dict | None = None):
    assert case.answers is not None
    case.output.mkdir(parents=True, exist_ok=True)
    return run_trivia_dungeon(
        "playthrough",
        root=case.root,
        config=case.config,
        dataset=case.dataset,
        contracts=case.contracts,
        answers=case.answers,
        output=case.output,
        state=case.state,
        cwd=cwd or case.root,
        env=env,
    )


def test_outputs_are_byte_reproducible_across_reruns_and_cwd(tmp_path: Path) -> None:
    """Audit and playthrough outputs are byte-identical across cwd and warm state."""
    bundled_state = APP_ROOT / ".state" / "audit-state.json"
    if bundled_state.exists():
        bundled_state.unlink()
    if DEFAULT_OUTPUT.exists():
        for child in DEFAULT_OUTPUT.iterdir():
            if child.is_file():
                child.unlink()
            else:
                shutil.rmtree(child)
    out_a = tmp_path / "out-a"
    out_b = tmp_path / "out-b"
    state_a = tmp_path / "state-a.json"
    state_b = tmp_path / "state-b.json"
    clear_directory(out_a)
    clear_directory(out_b)

    cold_audit = run_trivia_dungeon(
        "audit",
        root=APP_ROOT,
        config=BUNDLED_CONFIG,
        dataset=DATASET,
        contracts=CONTRACTS,
        output=out_a,
        state=state_a,
        cwd=APP_ROOT,
    )
    assert cold_audit.returncode == EXIT_SUCCESS, cold_audit.stderr
    cold_play = run_trivia_dungeon(
        "playthrough",
        root=APP_ROOT,
        config=BUNDLED_CONFIG,
        dataset=DATASET,
        contracts=CONTRACTS,
        answers=BUNDLED_ANSWERS,
        output=out_a,
        state=state_a,
        cwd=APP_ROOT,
    )
    assert cold_play.returncode == EXIT_SUCCESS, cold_play.stderr
    audit_bytes_cold = audit_report_path(out_a).read_bytes()
    play_bytes_cold = playthrough_report_path(out_a).read_bytes()

    warm_audit = run_trivia_dungeon(
        "audit",
        root=APP_ROOT,
        config=BUNDLED_CONFIG,
        dataset=DATASET,
        contracts=CONTRACTS,
        output=out_b,
        state=state_b,
        cwd=Path("/tmp"),
    )
    assert warm_audit.returncode == EXIT_SUCCESS, warm_audit.stderr
    warm_play = run_trivia_dungeon(
        "playthrough",
        root=APP_ROOT,
        config=BUNDLED_CONFIG,
        dataset=DATASET,
        contracts=CONTRACTS,
        answers=BUNDLED_ANSWERS,
        output=out_b,
        state=state_b,
        cwd=Path("/tmp"),
    )
    assert warm_play.returncode == EXIT_SUCCESS, warm_play.stderr

    audit_bytes_warm = audit_report_path(out_b).read_bytes()
    play_bytes_warm = playthrough_report_path(out_b).read_bytes()
    assert audit_bytes_cold == audit_bytes_warm
    assert play_bytes_cold == play_bytes_warm
    for payload in (audit_bytes_cold, play_bytes_cold):
        assert_canonical_json_bytes(payload)


def test_verify_target_succeeds_for_bundled_dungeon(tmp_path: Path) -> None:
    """Complete user-facing workflow: audit and playthrough exit 0 with clean reports."""
    state = APP_ROOT / ".state" / "test-bundled"
    if state.exists():
        state.unlink()
    if DEFAULT_OUTPUT.exists():
        for child in DEFAULT_OUTPUT.iterdir():
            if child.is_file():
                child.unlink()
            else:
                shutil.rmtree(child)

    audit_run = run_trivia_dungeon(
        "audit",
        output=DEFAULT_OUTPUT,
        state=state,
        cwd=APP_ROOT,
    )
    assert audit_run.returncode == EXIT_SUCCESS, audit_run.stdout + audit_run.stderr
    play_run = run_trivia_dungeon(
        "playthrough",
        output=DEFAULT_OUTPUT,
        state=state,
        answers=BUNDLED_ANSWERS,
        cwd=APP_ROOT,
    )
    assert play_run.returncode == EXIT_SUCCESS, play_run.stdout + play_run.stderr

    audit = _read_report(audit_report_path(DEFAULT_OUTPUT))
    play = _read_report(playthrough_report_path(DEFAULT_OUTPUT))
    assert_report_matches_schema_dir(audit, CONTRACTS)
    assert_playthrough_matches_schema_dir(play, CONTRACTS)
    assert_audit_success(audit)
    assert play["reached_exit"] is True
    assert audit["registry_digest"] == play["registry_digest"]
    bundled_state = APP_ROOT / ".state" / "audit-state.json"
    if bundled_state.exists():
        bundled_state.unlink()


def test_cli_environment_toml_precedence_and_relative_paths(tmp_path: Path) -> None:
    """CLI overrides env over TOML; TOML-relative paths resolve from config parent."""
    case = case_factory.build_precedence_case(tmp_path)
    env = {
        "TRIVIA_DATASET": str(case.notes["dataset_b"]),
        "TRIVIA_CONTRACTS": str(case.notes["contracts_b"]),
    }
    result = _run_audit(
        case,
        cwd=Path("/tmp"),
        env={
            **env,
            "TRIVIA_DATASET": str(case.dataset_a),
            "TRIVIA_CONTRACTS": str(case.contracts),
        },
    )
    assert result.returncode == EXIT_SUCCESS, result.stderr
    report = _read_report(audit_report_path(case.output))
    assert_audit_success(report)
    assert_posix_relative_artifacts(report)
    digest_a = dataset_digest(case.dataset_a)
    assert digest_a in json.dumps(report)


def test_yaml_12_json_scalar_semantics(tmp_path: Path) -> None:
    """Unquoted on/off/yes/no remain strings under YAML 1.2 semantics."""
    case = case_factory.build_yaml_scalar_case(tmp_path, seed=case_factory.SEED_YAML)
    result = _run_audit(case)
    assert result.returncode == EXIT_SUCCESS, result.stderr
    report = _read_report(audit_report_path(case.output))
    assert_audit_success(report)
    ids = {path.stem for path in (case.root / "bundle" / "chambers").glob("*.yaml") if path.name != "aliases.yaml"}
    assert "keywords" in ids or "on" in case.notes.get("keyword_room_ids", [])


def test_modern_question_id_requires_exactly_one_row(tmp_path: Path) -> None:
    """Stable IDs require exactly one dataset row."""
    case = case_factory.build_modern_id_case(tmp_path, seed=case_factory.SEED_SCHEMA)
    result = _run_audit(case)
    assert result.returncode == EXIT_CONTENT, result.stderr
    report = _read_report(audit_report_path(case.output))
    assert_issue_sets_equal(case.expected_issues, issue_tuples(report))


def test_legacy_locator_is_stable_under_physical_reorder(tmp_path: Path) -> None:
    """Legacy row locators use canonical order, not Parquet scan order."""
    bundled_state = APP_ROOT / ".state" / "audit-state.json"
    bundled_state.unlink(missing_ok=True)
    case_a, case_b = case_factory.build_legacy_reorder_case(tmp_path, seed=case_factory.SEED_YAML)
    res_a = _run_audit(case_a)
    res_b = _run_audit(case_b)
    assert res_a.returncode == EXIT_SUCCESS, res_a.stderr
    assert res_b.returncode == EXIT_SUCCESS, res_b.stderr
    report_a = _read_report(audit_report_path(case_a.output))
    report_b = _read_report(audit_report_path(case_b.output))
    assert report_a["registry_digest"] == report_b["registry_digest"]
    assert case_a.notes["question_id"] == case_b.notes["question_id"]
    assert case_a.notes["dataset_digest"] != case_b.notes["dataset_digest"]


def test_stale_legacy_fingerprint_is_rejected(tmp_path: Path) -> None:
    """Row index alone is insufficient; fingerprint must match canonical question text."""
    case = case_factory.build_stale_fingerprint_case(tmp_path, seed=case_factory.SEED_SCHEMA)
    result = _run_audit(case)
    assert result.returncode == EXIT_CONTENT, result.stderr
    report = _read_report(audit_report_path(case.output))
    assert_issue_sets_equal(case.expected_issues, issue_tuples(report))


def test_state_invalidates_on_manifest_contract_and_dataset_content(tmp_path: Path) -> None:
    """Content-addressed state invalidates manifest, contract, and dataset mutations."""
    case = case_factory.build_valid_dungeon(tmp_path, seed=case_factory.SEED_YAML)
    warm = _run_audit(case)
    assert warm.returncode == EXIT_SUCCESS, warm.stderr
    warm_report = _read_report(audit_report_path(case.output))
    warm_digest = warm_report["input_digest"]

    room = next((case.root / "bundle" / "chambers").glob("*.yaml"))
    original = room.read_bytes()
    mutated = original.replace(b"title", b"titles", 1)
    if mutated == original:
        mutated = original + b"\n"
    room.write_bytes(mutated)
    os.utime(room, (1_600_000_000, 1_600_000_000))
    after_manifest = _run_audit(case)
    assert after_manifest.returncode in (EXIT_SUCCESS, EXIT_CONTENT)
    after_report = _read_report(audit_report_path(case.output))
    assert after_report["input_digest"] != warm_digest

    room.write_bytes(original)
    schema = case.contracts / "room.schema.json"
    schema_orig = schema.read_bytes()
    schema.write_bytes(schema_orig + b" ")
    os.utime(schema, (1_600_000_000, 1_600_000_000))
    _run_audit(case)
    after_contract_report = _read_report(audit_report_path(case.output))
    assert after_contract_report["input_digest"] != warm_digest
    schema.write_bytes(schema_orig)

    data_orig = case.dataset.read_bytes()
    case.dataset.write_bytes(data_orig + b"\0")
    os.utime(case.dataset, (1_600_000_000, 1_600_000_000))
    _run_audit(case)
    after_data_report = _read_report(audit_report_path(case.output))
    assert after_data_report["input_digest"] != warm_digest
    case.dataset.write_bytes(data_orig)


def test_failed_or_truncated_state_is_never_reused(tmp_path: Path) -> None:
    """Failed audits and truncated state files are not treated as reusable success."""
    case = case_factory.build_aggregated_errors_case(tmp_path, seed=case_factory.SEED_SCHEMA)
    first = _run_audit(case)
    assert first.returncode == EXIT_CONTENT
    if case.state.exists():
        state = load_json(case.state)
        assert state.get("success") is not True

    case.state.parent.mkdir(parents=True, exist_ok=True)
    case.state.write_text('{"format_version":"1","input_digest":"abc","success":true,"registry":', encoding="utf-8")
    valid = case_factory.build_valid_dungeon(tmp_path / "repaired", seed=case_factory.SEED_SCHEMA)
    repaired = _run_audit(valid)
    assert repaired.returncode == EXIT_SUCCESS, repaired.stderr
    state_doc = load_json(valid.state)
    assert state_doc.get("success") is True
    assert "registry" in state_doc


@pytest.mark.parametrize("seed", [173, 811, 20260711])
def test_generated_valid_case_changes_counts_and_paths(tmp_path: Path, seed: int) -> None:
    """Seeded valid dungeons vary counts and paths; reports match reference expectations."""
    case = case_factory.build_valid_dungeon(tmp_path, seed=seed)
    audit = _run_audit(case)
    assert audit.returncode == EXIT_SUCCESS, audit.stderr
    play = _run_playthrough(case)
    assert play.returncode == EXIT_SUCCESS, play.stderr
    audit_report = _read_report(audit_report_path(case.output))
    play_report = _read_report(playthrough_report_path(case.output))
    assert len(audit_report.get("artifacts", [])) > 0
    assert play_report["reached_exit"] is True
    if case.expected_score is not None:
        assert play_report["total_score"] == case.expected_score
    if case.expected_route is not None:
        assert play_report["visited_rooms"] == case.expected_route
    for issue in audit_report.get("issues", []):
        assert not Path(issue["artifact"]).is_absolute()


def test_immutable_inputs_are_unchanged(fixture_hashes: dict[str, str]) -> None:
    """Bundled dataset and contracts remain byte-identical and non-writable."""
    assert_immutable_hashes(fixture_hashes)
    _run_audit(
        case_factory.DungeonCase(
            root=APP_ROOT,
            config=BUNDLED_CONFIG,
            dataset=DATASET,
            contracts=CONTRACTS,
            answers=None,
            state=APP_ROOT / ".state" / "hash-check.json",
            output=DEFAULT_OUTPUT,
            description="hash guard",
        )
    )
    assert_immutable_hashes(fixture_hashes)
    data_path = Path("/data/trivia_qa_sample.parquet")
    mode = data_path.stat().st_mode
    assert not (mode & stat.S_IWOTH), "/data must not be world-writable"


def test_invalid_operational_inputs_use_exit_one_without_fake_validation_report(tmp_path: Path) -> None:
    """Operational failures exit 1 without claiming a completed content audit."""
    out = tmp_path / "operational-out"
    state = tmp_path / "operational-state.json"

    missing_ds = run_trivia_dungeon(
        "audit",
        dataset=tmp_path / "missing.parquet",
        output=out / "a",
        state=state,
    )
    assert missing_ds.returncode == EXIT_OPERATIONAL
    assert_no_completed_audit_on_operational_failure(out / "a", missing_ds.stderr)

    blocked_parent = tmp_path / "blocked"
    blocked_parent.mkdir()
    blocked_parent.chmod(0o500)
    try:
        bad_out = run_trivia_dungeon(
            "audit",
            output=blocked_parent / "child" / "nested",
            state=tmp_path / "state-b.json",
        )
        assert bad_out.returncode == EXIT_OPERATIONAL
    finally:
        blocked_parent.chmod(0o700)

    bad_state = tmp_path / "not-a-dir" / "state.json"
    bad_state.parent.write_text("file", encoding="utf-8")
    bad_state_run = run_trivia_dungeon(
        "audit",
        output=tmp_path / "out-c",
        state=bad_state,
    )
    assert bad_state_run.returncode == EXIT_OPERATIONAL


def test_fingerprint_matches_domain_contract() -> None:
    """Sanity: verifier fingerprint matches domain-contract formula."""
    rows = canonical_rows(DATASET)
    assert rows, "bundled dataset must contain rows"
    sample = rows[0]
    assert question_fingerprint(sample["question"]) == sample["question_sha256"]
