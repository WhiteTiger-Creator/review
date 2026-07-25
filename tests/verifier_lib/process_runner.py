"""Subprocess wrapper for signingd's public CLI."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

APP = Path("/app")
CURRENT = APP / "config/current.toml"
LEGACY = APP / "config/legacy.toml"


@dataclass
class Result:
    returncode: int
    stdout: str
    stderr: str


def binary() -> str:
    for path in (APP / "bin/signingd", APP / "target/release/signingd"):
        if path.is_file():
            return str(path)
    raise AssertionError("signingd binary not found")


def run(config: Path = CURRENT, command: str = "run",
        softhsm_conf: Path | None = None) -> Result:
    """Run signingd with SoftHSM configuration and captured text output."""
    result = subprocess.run(
        [binary(), command, "--config", str(config)], text=True, capture_output=True,
        env={**os.environ, "SOFTHSM2_CONF": str(softhsm_conf or APP / "config/softhsm2.conf")},
        timeout=45,
        check=False,
    )
    return Result(result.returncode, result.stdout, result.stderr)
