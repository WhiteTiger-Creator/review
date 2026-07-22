"""Merge verifier phase CTRF reports into the canonical report path."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def empty_report() -> dict:
    return {
        "results": {
            "tool": {"name": "pytest", "version": "unknown"},
            "summary": {
                "tests": 0,
                "passed": 0,
                "failed": 1,
                "skipped": 0,
                "pending": 0,
                "other": 0,
                "start": 0,
                "stop": 0,
            },
            "tests": [
                {
                    "name": "verifier::no_pytest_phase_completed",
                    "status": "failed",
                    "duration": 0,
                    "start": 0,
                    "stop": 0,
                    "retries": 0,
                    "file_path": "test.sh",
                    "trace": "Verifier failed before a pytest phase completed.",
                }
            ],
        }
    }


def main() -> None:
    out_path = Path(sys.argv[1])
    inputs = [Path(arg) for arg in sys.argv[2:]]
    labels = ["public", "hidden_1", "hidden_2"]
    reports = [(label, json.loads(path.read_text())) for label, path in zip(labels, inputs) if path.exists()]

    if not reports:
        out_path.write_text(json.dumps(empty_report(), indent=2) + "\n")
        return

    merged = reports[0][1]
    results = merged["results"]
    summary = results["summary"]
    tests = []
    for label, report in reports:
        for test in report["results"].get("tests", []):
            item = dict(test)
            item["name"] = f"{label}::{item.get('name', 'unnamed')}"
            tests.append(item)

    results["tests"] = tests
    for key in ("tests", "passed", "failed", "skipped", "pending", "other"):
        summary[key] = sum(int(report["results"]["summary"].get(key, 0)) for _, report in reports)
    summary["start"] = min(float(report["results"]["summary"].get("start", 0)) for _, report in reports)
    summary["stop"] = max(float(report["results"]["summary"].get("stop", 0)) for _, report in reports)
    out_path.write_text(json.dumps(merged, indent=2) + "\n")


if __name__ == "__main__":
    main()
