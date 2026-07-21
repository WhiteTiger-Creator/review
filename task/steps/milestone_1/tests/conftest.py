"""Session-scoped notes_server lifecycle for HTTP verifier tests."""

from __future__ import annotations

import os
import signal
import subprocess
import time
import urllib.error
import urllib.request

import pytest

_SERVER_URL = "http://127.0.0.1:8080/api/notes"


def _wait_for_server(timeout_sec: float = 20.0) -> None:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(_SERVER_URL, timeout=2)
            return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.5)
    raise RuntimeError("notes_server did not become ready on port 8080")


@pytest.fixture(scope="session", autouse=True)
def notes_server() -> None:
    os.makedirs("/app/data", exist_ok=True)
    if not os.path.isfile("/app/notes_server"):
        subprocess.run(["make"], cwd="/app", check=False)

    proc: subprocess.Popen[bytes] | None = None
    if os.path.isfile("/app/notes_server"):
        db_path = "/app/data/notes.db"
        if os.path.isfile(db_path):
            os.remove(db_path)
        proc = subprocess.Popen(["/app/notes_server"])
        _wait_for_server()

    yield

    if proc is not None and proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
