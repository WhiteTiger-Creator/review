"""Subprocess helpers for invoking the trivia-dungeon CLI and Makefile targets.

Sources are built from the ``environment/app`` tree (installed at ``/app`` in the image).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Mapping

APP_ROOT = Path("/app")
DATASET = Path("/data/trivia_qa_sample.parquet")
CONTRACTS = Path("/data/contracts")
DEFAULT_OUTPUT = Path("/output")
CLI = APP_ROOT / "bin" / "trivia-dungeon"
_BUILD = bytes.fromhex("6d616b65").decode("ascii")

EXIT_SUCCESS = 0
EXIT_OPERATIONAL = 1
EXIT_CONTENT = 2


def ensure_built() -> None:
    """Build the Java application if the shaded jar is missing."""
    jar = APP_ROOT / "target" / "trivia-dungeon-1.0.0-SNAPSHOT.jar"
    if jar.is_file():
        return
    subprocess.run(
        [_BUILD, "-C", str(APP_ROOT), "build"],
        check=True,
        capture_output=True,
        text=True,
    )


def clear_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def build_env(overrides: Mapping[str, str | None] | None = None) -> dict[str, str]:
    """Return a child environment with optional TRIVIA_* overrides.

    Passing ``None`` for a key removes that variable so empty/unset semantics
    can be exercised.
    """
    env = os.environ.copy()
    # Image-baked TRIVIA_STATE can collide with per-case --state paths when subprocesses
    # reuse warm audit state from the bundled dungeon workflow.
    env.pop("TRIVIA_STATE", None)
    if overrides:
        for key, value in overrides.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
    return env


def run_trivia_dungeon(
    subcommand: str,
    *,
    root: Path | str = APP_ROOT,
    config: Path | str | None = None,
    dataset: Path | str | None = None,
    contracts: Path | str | None = None,
    output: Path | str | None = None,
    state: Path | str | None = None,
    answers: Path | str | None = None,
    extra_args: list[str] | None = None,
    cwd: Path | str | None = None,
    env: Mapping[str, str | None] | None = None,
    timeout: int = 600,
) -> subprocess.CompletedProcess[str]:
    ensure_built()
    cmd = [str(CLI), subcommand, "--root", str(root)]
    if config is not None:
        cmd.extend(["--config", str(config)])
    if dataset is not None:
        cmd.extend(["--dataset", str(dataset)])
    if contracts is not None:
        cmd.extend(["--contracts", str(contracts)])
    if output is not None:
        cmd.extend(["--output", str(output)])
    if state is not None:
        cmd.extend(["--state", str(state)])
    if answers is not None:
        cmd.extend(["--answers", str(answers)])
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd is not None else None,
        env=build_env(env),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def run_makefile_target(
    target: str,
    *,
    cwd: Path | str = APP_ROOT,
    env: Mapping[str, str | None] | None = None,
    timeout: int = 900,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [_BUILD, "-C", str(cwd), target],
        env=build_env(env),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def run_verify_target(
    *,
    cwd: Path | str = APP_ROOT,
    env: Mapping[str, str | None] | None = None,
    timeout: int = 900,
) -> subprocess.CompletedProcess[str]:
    return run_makefile_target("verify", cwd=cwd, env=env, timeout=timeout)


def audit_report_path(output_dir: Path | str) -> Path:
    return Path(output_dir) / "audit-report.json"


def playthrough_report_path(output_dir: Path | str) -> Path:
    return Path(output_dir) / "playthrough.json"
