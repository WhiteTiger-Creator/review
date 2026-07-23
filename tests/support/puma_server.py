"""Start and stop the Rails service for HTTP tests."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

import requests

APP = Path("/app")


class PumaServer:
    def __init__(self, *, remote_url: str, cache_root: str, port: int = 3000, allowed_signer: str | None = None):
        self.remote_url = remote_url
        self.cache_root = cache_root
        self.port = port
        self.allowed_signer = allowed_signer
        self.proc: subprocess.Popen[str] | None = None

    def __enter__(self) -> "PumaServer":
        env = os.environ.copy()
        env.update(
            {
                "CORPUS_REMOTE_URL": self.remote_url,
                "CORPUS_CACHE_ROOT": self.cache_root,
                "PORT": str(self.port),
                "RAILS_ENV": "development",
            }
        )
        if self.allowed_signer:
            env["CORPUS_ALLOWED_SIGNER"] = self.allowed_signer
        self.proc = subprocess.Popen(
            ["bundle", "exec", "puma", "-C", "config/puma.rb", "-b", f"tcp://127.0.0.1:{self.port}"],
            cwd=str(APP),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(60):
            try:
                resp = requests.get(f"http://127.0.0.1:{self.port}/up", timeout=1)
                if resp.status_code == 200:
                    return self
            except requests.RequestException:
                pass
            time.sleep(0.5)
        raise RuntimeError("puma failed to become ready")

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"
