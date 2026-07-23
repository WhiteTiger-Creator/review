"""JSON schema validation, canonical JSON checks, and issue tuple comparisons."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

IssueTuple = tuple[str, str, str]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    read_chunk = 64 << 10
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(read_chunk), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_against_schema(document: Any, schema_path: Path) -> None:
    schema = load_json(schema_path)
    Draft202012Validator(schema).validate(document)


def assert_valid_report(document: Any, schema_path: Path) -> None:
    validate_against_schema(document, schema_path)


def assert_canonical_json_bytes(raw: bytes) -> None:
    text = raw.decode("utf-8")
    assert text.endswith("\n"), "canonical JSON must end with a single trailing newline"
    assert not text.endswith("\n\n"), "canonical JSON must not have multiple trailing newlines"
    assert "/tmp/" not in text, "output must not embed temporary absolute paths"
    parsed = json.loads(text)
    assert _object_keys_sorted(parsed), "object keys must be lexicographically sorted at every level"
    _assert_sorted_keys_recursive(parsed)


def _object_keys_sorted(value: Any) -> bool:
    if isinstance(value, dict):
        keys = list(value.keys())
        if keys != sorted(keys):
            return False
        return all(_object_keys_sorted(v) for v in value.values())
    if isinstance(value, list):
        return all(_object_keys_sorted(item) for item in value)
    return True


def _assert_sorted_keys_recursive(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        keys = list(value.keys())
        assert keys == sorted(keys), f"unsorted object keys at {path}: {keys}"
        for key in keys:
            _assert_sorted_keys_recursive(value[key], f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_sorted_keys_recursive(item, f"{path}[{index}]")


def issue_tuples(report: dict[str, Any]) -> list[IssueTuple]:
    issues = report.get("issues", [])
    tuples = [
        (issue["artifact"], issue["pointer"], issue["code"])
        for issue in issues
    ]
    # canonical ordering for comparison: artifact, pointer, code
    return sorted(tuples)


def assert_issue_sets_equal(
    expected: Iterable[IssueTuple],
    actual: Iterable[IssueTuple],
) -> None:
    exp = sorted(expected)
    got = sorted(actual)
    assert exp == got, f"issue tuple mismatch\nexpected: {exp}\nactual:   {got}"


def assert_audit_success(report: dict[str, Any]) -> None:
    assert report.get("success") is True, report
    assert report.get("issue_count") == 0, report
    assert issue_tuples(report) == [], report


def assert_posix_relative_artifacts(report: dict[str, Any]) -> None:
    for issue in report.get("issues", []):
        artifact = issue["artifact"]
        assert not artifact.startswith("/"), f"artifact path must be root-relative: {artifact}"
        assert "\\" not in artifact, f"artifact path must use POSIX separators: {artifact}"
    for artifact in report.get("artifacts", []):
        assert not str(artifact).startswith("/"), artifact
        assert "\\" not in str(artifact), artifact


def load_fixture_hashes(path: Path) -> dict[str, str]:
    return load_json(path)


def assert_immutable_hashes(
    fixture_hashes: dict[str, str],
    *,
    data_root: Path = Path("/data"),
) -> None:
    for rel_path, expected in sorted(fixture_hashes.items()):
        if rel_path.startswith("contracts/"):
            full = data_root / rel_path
        elif rel_path.startswith("data/"):
            full = Path("/") / rel_path
        else:
            full = data_root / rel_path
        actual = sha256_file(full)
        assert actual == expected, f"hash mismatch for {full}: {actual} != {expected}"


def assert_issue_count_consistent(report: dict[str, Any]) -> None:
    issues = report.get("issues", [])
    assert report.get("issue_count") == len(issues)
    if report.get("success"):
        assert len(issues) == 0


def extract_registry_digest_pair(
    audit_report: dict[str, Any],
    playthrough_report: dict[str, Any],
) -> None:
    assert audit_report["registry_digest"] == playthrough_report["registry_digest"]


def assert_no_completed_audit_on_operational_failure(
    output_dir: Path,
    stderr: str,
) -> None:
    report_path = output_dir / "audit-report.json"
    if not report_path.exists():
        return
    report = load_json(report_path)
    if report.get("success"):
        raise AssertionError(
            "operational failure must not emit a successful completed audit report: "
            f"{report_path}\nstderr={stderr}"
        )
    if report.get("issue_count", 0) > 0 and not report.get("artifacts"):
        raise AssertionError("operational failure produced a fake validation report")


def help_text_mentions(substrings: Iterable[str], text: str) -> None:
    for item in substrings:
        assert item in text, f"missing help text fragment: {item}"


def assert_dataset_digest_in_report(report: dict[str, Any], dataset_path: Path) -> None:
    digest = sha256_file(dataset_path)
    serialized = json.dumps(report)
    assert digest in serialized or report.get("input_digest"), (
        "report should reflect dataset identity via input_digest or embedded digest"
    )


def normalize_pointer(pointer: str) -> str:
    if pointer == "":
        return ""
    return pointer if pointer.startswith("/") else f"/{pointer}"


def issue_codes(report: dict[str, Any]) -> set[str]:
    return {code for _, _, code in issue_tuples(report)}


def assert_report_matches_schema_dir(report: dict[str, Any], contracts_dir: Path) -> None:
    validate_against_schema(report, contracts_dir / "audit-report.schema.json")


def assert_playthrough_matches_schema_dir(report: dict[str, Any], contracts_dir: Path) -> None:
    validate_against_schema(report, contracts_dir / "playthrough.schema.json")
