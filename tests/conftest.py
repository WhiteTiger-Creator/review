"""Host path shims when pytest runs outside the Docker /app layout."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def _host_app_paths() -> None:
    if Path("/app/data").is_dir():
        return
    import test_outputs as tv

    root = Path(__file__).resolve().parents[1]
    tv.DATA_DIR = root / "environment" / "data"
    tv.OUT_DIR = root / ".host_output"
    tv.PROJECT_DIR = root / "environment" / "trust-remediator"
    tv.BIN_PATH = tv.PROJECT_DIR / "build" / "trust_attest"
    tv.OUT_DIR.mkdir(exist_ok=True)
