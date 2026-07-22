"""Minimal pytest CTRF writer for the anuran task."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--ctrf", action="store", default=None, help="write CTRF JSON to PATH")


def pytest_configure(config: pytest.Config) -> None:
    config._anuran_ctrf_started = time.time()  # type: ignore[attr-defined]


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    path = session.config.getoption("ctrf")
    if not path:
        return

    reporter = session.config.pluginmanager.getplugin("terminalreporter")
    stats = getattr(reporter, "stats", {}) if reporter is not None else {}
    passed = len(stats.get("passed", []))
    failed = len(stats.get("failed", []))
    skipped = len(stats.get("skipped", []))
    pending = len(stats.get("xfailed", [])) + len(stats.get("xpassed", []))
    tests = passed + failed + skipped + pending
    started = float(getattr(session.config, "_anuran_ctrf_started", time.time()))
    finished = time.time()

    report = {
        "results": {
            "tool": {"name": "pytest", "version": pytest.__version__},
            "summary": {
                "tests": tests,
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "pending": pending,
                "other": 0,
                "start": started,
                "stop": finished,
            },
            "tests": [],
        }
    }
    Path(path).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
