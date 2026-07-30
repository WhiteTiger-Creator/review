"""Native HTTP fixtures and lifecycle helpers for mirrorveil verification."""

from __future__ import annotations

import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

ROOT = Path("/srv/mirrorveil")
BIN = ROOT / "bin"
RUNTIME = ROOT / "runtime"
CONTROL_ENV = ROOT / "policy" / "control.conf"

CACHE = "http://127.0.0.1:18091"
HOST_AURORA = "releases.aurora.invalid"
HOST_BASALT = "releases.basalt.invalid"


@dataclass
class HttpResult:
    status: int
    headers: dict[str, str]
    body: bytes


def _load_control_marker() -> str:
    for line in CONTROL_ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith("CONTROL_MARKER="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("CONTROL_MARKER missing")


def run_cmd(args: list[str], *, check: bool = True, timeout: float = 120.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=check,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def start_stack() -> None:
    run_cmd([str(BIN / "start-cache-stack")])
    run_cmd([str(BIN / "wait-for-cache"), "stack-ready"], timeout=90.0)


def stop_stack() -> None:
    run_cmd([str(BIN / "stop-cache-stack")], check=False)


def reset_stack() -> None:
    stop_stack()
    # Clear varnish storage workspace but preserve secret if present.
    work = RUNTIME / "varnish"
    if work.exists():
        for path in work.iterdir():
            if path.name == "secret":
                continue
            if path.is_file() or path.is_symlink():
                path.unlink(missing_ok=True)
    for log in (
        RUNTIME / "primary" / "logs" / "access.log",
        RUNTIME / "secondary" / "logs" / "access.log",
    ):
        if log.exists():
            log.write_text("", encoding="utf-8")
    start_stack()


def cache_control(*args: str) -> str:
    proc = run_cmd([str(BIN / "cache-control"), *args])
    return proc.stdout


def wait_for(condition: str, timeout: float = 60.0) -> None:
    run_cmd([str(BIN / "wait-for-cache"), condition], timeout=timeout)


def force_backend_health(backend: str, state: str) -> None:
    """Set Varnish backend health immediately (sick|healthy|auto)."""
    run_cmd(
        ["varnishadm", "-n", str(RUNTIME / "varnish"), "backend.set_health", backend, state],
        check=False,
    )


def inspect_cache() -> str:
    return run_cmd([str(BIN / "inspect-cache")]).stdout


def reload_policy() -> subprocess.CompletedProcess[str]:
    return run_cmd([str(BIN / "reload-cache-policy")], check=False)


def http_request(
    method: str,
    url: str,
    *,
    host: str,
    headers: Mapping[str, str] | None = None,
    body: bytes | None = None,
    timeout: float = 10.0,
) -> HttpResult:
    hdrs = {"Host": host}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw_headers = {k.lower(): v for k, v in resp.headers.items()}
            return HttpResult(status=resp.status, headers=raw_headers, body=resp.read())
    except urllib.error.HTTPError as exc:
        raw_headers = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
        return HttpResult(status=exc.code, headers=raw_headers, body=exc.read())


def edge_get(path: str, host: str = HOST_AURORA, **kwargs: object) -> HttpResult:
    headers = kwargs.pop("headers", None)
    method = str(kwargs.pop("method", "GET"))
    assert not kwargs
    return http_request(method, f"{CACHE}{path}", host=host, headers=headers)  # type: ignore[arg-type]


def edge_state(result: HttpResult) -> str:
    return result.headers.get("x-edge-state", "")


def origin_node(result: HttpResult) -> str:
    return result.headers.get("x-origin-node", "")


def count_access_hits(origin: str, needle: str) -> int:
    log = RUNTIME / origin / "logs" / "access.log"
    if not log.exists():
        return 0
    return sum(1 for line in log.read_text(encoding="utf-8", errors="replace").splitlines() if needle in line)


def truncate_access_logs() -> None:
    for origin in ("primary", "secondary"):
        log = RUNTIME / origin / "logs" / "access.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("", encoding="utf-8")


def control_headers(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    hdrs = {"X-Mirror-Control": _load_control_marker()}
    if extra:
        hdrs.update(extra)
    return hdrs


def active_vcl_label() -> str:
    out = run_cmd(
        ["varnishadm", "-n", str(RUNTIME / "varnish"), "vcl.list"],
        check=False,
    ).stdout
    for line in out.splitlines():
        parts = line.split()
        if not parts or parts[0] != "active":
            continue
        # Prefer an explicit mv_* / boot token anywhere on the active row.
        for part in reversed(parts):
            if part.startswith("mv_") or part in {"boot", "boot_reload"}:
                # Strip optional varnish temp suffixes after a second underscore block
                # when the token is already the loaded name (mv_<16hex>).
                if part.startswith("mv_") and len(part) >= 19:
                    # mv_ + 16 hex == 19 chars; ignore longer generated aliases
                    maybe = part[:19]
                    if re.fullmatch(r"mv_[0-9a-f]{16}", maybe):
                        return maybe
                return part
        return parts[-1]
    return ""


def vcl_list() -> str:
    return run_cmd(
        ["varnishadm", "-n", str(RUNTIME / "varnish"), "vcl.list"],
        check=False,
    ).stdout


def sleep_seconds(seconds: float) -> None:
    time.sleep(seconds)


def stage_broken_vcl(target: Path) -> Path:
    backup = target.with_suffix(target.suffix + ".bak_rangehouse")
    backup.write_bytes(target.read_bytes())
    target.write_text(
        target.read_text(encoding="utf-8") + "\nthis is not valid vcl syntax !!!\n",
        encoding="utf-8",
    )
    return backup


def restore_file(backup: Path, target: Path) -> None:
    target.write_bytes(backup.read_bytes())
    backup.unlink(missing_ok=True)


def ensure_env_path() -> None:
    os.environ["PATH"] = f"/srv/mirrorveil/bin:/opt/verifier_venv/bin:{os.environ.get('PATH', '')}"
