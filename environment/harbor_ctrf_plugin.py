"""Small offline pytest plugin that writes a CTRF-compatible summary."""
from __future__ import annotations

import json
from pathlib import Path

_RESULTS: list[dict[str, object]] = []


def pytest_addoption(parser):
    """Register the CTRF output option expected by the verifier runner."""
    parser.addoption("--ctrf", action="store", default=None, help="write CTRF JSON")


def pytest_sessionstart(session):
    """Reset captured reports for each pytest session."""
    _RESULTS.clear()


def pytest_runtest_logreport(report):
    """Capture one call-phase result in a compact neutral structure."""
    if report.when != "call":
        return
    _RESULTS.append(
        {
            "name": report.nodeid,
            "status": "passed" if report.passed else "failed" if report.failed else "skipped",
            "duration": round(report.duration * 1000, 3),
        }
    )


def pytest_sessionfinish(session, exitstatus):
    """Write a deterministic CTRF-compatible summary after test execution."""
    target = session.config.getoption("--ctrf")
    if not target:
        return
    counts = {"passed": 0, "failed": 0, "skipped": 0, "pending": 0, "other": 0}
    for item in _RESULTS:
        counts[str(item["status"])] += 1
    payload = {
        "results": {
            "tool": {"name": "pytest", "version": "system"},
            "summary": {"tests": len(_RESULTS), **counts},
            "tests": _RESULTS,
        }
    }
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
