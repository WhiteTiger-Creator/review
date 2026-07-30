"""Pytest configuration for mirrorveil native verification."""

from __future__ import annotations

import pytest
from varnish_rangehouse import ensure_env_path, reset_stack, stop_stack


@pytest.fixture(autouse=True)
def _isolate_stack() -> None:
    ensure_env_path()
    reset_stack()
    yield
    stop_stack()
