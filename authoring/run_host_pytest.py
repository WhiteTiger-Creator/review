#!/usr/bin/env python3
"""Host-side pytest driver with /app path shims. Authoring only."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / "environment"
OUT = ROOT / ".host_output"


def patch_module() -> None:
    spec = importlib.util.spec_from_file_location(
        "test_outputs", ROOT / "tests" / "test_outputs.py"
    )
    tv = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(tv)
    tv.DATA_DIR = ENV / "data"
    tv.OUT_DIR = OUT
    tv.PROJECT_DIR = ENV / "trust-remediator"
    tv.BIN_PATH = tv.PROJECT_DIR / "build" / "trust_attest"
    sys.modules["test_outputs"] = tv


def main() -> int:
    OUT.mkdir(exist_ok=True)
    patch_module()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "tests")
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(ROOT / "tests" / "test_outputs.py"),
        "-q",
        "--tb=no",
        *sys.argv[1:],
    ]
    return subprocess.call(cmd, cwd=ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
