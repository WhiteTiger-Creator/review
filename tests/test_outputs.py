"""Verifier for rust-framekit-length-underflow-audit.

The agent writes one verdict per evidence case to /app/verdicts.txt. This
verifier recomputes the ground-truth verdict for every case straight from the
raw evidence in environment/cases.jsonl, using an independent from-scratch
Python reimplementation of the frame-format contract (tests/_lib/oracle.py),
and compares the agent's finding against it byte for byte. No answer key ships
in the environment, so a verdict can only be produced by actually carrying the
dispatch gate and the double-wrapping arithmetic through, not by copying. The
disclosed teaching set in environment/examples.jsonl is checked for internal
consistency against the same oracle so the two manifests cannot drift apart.
"""

import importlib.util
from pathlib import Path

import pytest

ENV = Path("/app/environment")
CASES_PATH = ENV / "cases.jsonl"
EXAMPLES_PATH = ENV / "examples.jsonl"
FINDINGS_PATH = Path("/app/verdicts.txt")

_oracle_spec = importlib.util.spec_from_file_location(
    "oracle", Path(__file__).resolve().parent / "_lib" / "oracle.py"
)
oracle = importlib.util.module_from_spec(_oracle_spec)
_oracle_spec.loader.exec_module(oracle)


def _frame(case):
    return bytes.fromhex(case["frame_hex"])


def _load_findings():
    assert FINDINGS_PATH.exists(), f"no findings file at {FINDINGS_PATH}"
    findings = {}
    for lineno, raw in enumerate(FINDINGS_PATH.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        assert len(parts) == 2, f"line {lineno}: expected '<id> <verdict>', got {raw!r}"
        cid, verdict = parts[0], parts[1].strip()
        assert cid not in findings, f"duplicate finding for case {cid!r}"
        findings[cid] = verdict
    return findings


CASES = oracle.load_cases(CASES_PATH) if CASES_PATH.exists() else []
CASE_IDS = [c["id"] for c in CASES]
CASE_BY_ID = {c["id"]: c for c in CASES}
EXAMPLES = oracle.load_cases(EXAMPLES_PATH) if EXAMPLES_PATH.exists() else []


def test_evidence_present():
    """The graded evidence manifest ships at least the full held-out case set."""
    assert len(CASES) >= 60, f"expected the full evidence manifest, found {len(CASES)}"


def test_findings_file_present():
    """The agent produced a findings file with a verdict for every case."""
    findings = _load_findings()
    missing = [cid for cid in CASE_IDS if cid not in findings]
    assert not missing, f"no verdict emitted for: {missing[:10]}"


def test_all_verdict_classes_exercised():
    """The evidence spans every verdict class, witness ranges included."""
    kinds = {oracle.classify(c["config_text"], _frame(c)).split(":")[0] for c in CASES}
    assert kinds == set(oracle.VERDICTS), f"missing verdict classes: {set(oracle.VERDICTS) - kinds}"


@pytest.mark.parametrize("cid", CASE_IDS)
def test_case_verdict_matches_oracle(cid):
    """Each emitted verdict matches the independent oracle for that case."""
    findings = _load_findings()
    case = CASE_BY_ID[cid]
    expected = oracle.classify(case["config_text"], _frame(case))
    assert cid in findings, f"{cid}: no verdict emitted"
    assert findings[cid] == expected, f"{cid}: got {findings[cid]!r}, want {expected!r}"


@pytest.mark.parametrize("ex", EXAMPLES, ids=[e["id"] for e in EXAMPLES])
def test_examples_are_self_consistent(ex):
    """Every disclosed teaching answer equals what the oracle recomputes."""
    expected = oracle.classify(ex["config_text"], _frame(ex))
    assert ex["expected"] == expected, f"{ex['id']}: teaching answer {ex['expected']!r} != oracle {expected!r}"
