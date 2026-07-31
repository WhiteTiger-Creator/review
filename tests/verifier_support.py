"""Independent semantic model helpers for GraphRunSigner verifier tests."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import time
import unicodedata
from decimal import Decimal
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

VERIFIER_ROOT = Path(os.environ.get("TERMINUS_VERIFIER_ROOT", "/tmp/terminus-verifier"))
APP_ROOT = Path("/app/pkg")
SCRIPTS = Path("/app/pkg/ops")
DATA_RUNS = Path("/data/runs")
DATA_KEYS = Path("/data/keys")
OUTPUT = Path("/output")


def frame(fields: list[str]) -> bytes:
    out = bytearray()
    for field in fields:
        raw = field.encode("utf-8")
        out += len(raw).to_bytes(4, "big") + raw
    return bytes(out)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def normalize_weight(raw: str) -> str:
    value = raw.strip()
    if value.startswith("."):
        value = "0" + value
    decimal = Decimal(value).normalize()
    text = format(decimal, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def utf8_lt(a: str, b: str) -> bool:
    return a.encode("utf-8") < b.encode("utf-8")


def graph_digest(graph: dict[str, Any]) -> str:
    undirected = graph.get("graph_type") == "undirected"
    nodes = sorted({nfc(node["id"]) for node in graph.get("nodes", [])})
    edge_records: set[str] = set()
    for edge in graph.get("edges", []):
        source = nfc(edge["source"])
        target = nfc(edge["target"])
        if (
            undirected
            and source != target
            and not utf8_lt(source, target)
            and source.encode("utf-8") > target.encode("utf-8")
        ):
            source, target = target, source
        attrs = edge.get("attributes")
        attrs_json = "" if attrs is None else json.dumps(attrs, sort_keys=True, separators=(",", ":"))
        record = "\0".join(
            [
                source,
                target,
                edge.get("kind", ""),
                normalize_weight(str(edge.get("weight", "0"))),
                attrs_json,
            ]
        )
        edge_records.add(record)
    fields = [
        "GRAPHRUN.GRAPH.v1",
        graph.get("graph_id", ""),
        graph.get("graph_type", ""),
        "\n".join(nodes),
        *sorted(edge_records),
    ]
    return sha256_hex(frame(fields))


def run_digest(run: dict[str, Any]) -> str:
    def sorted_kv(obj: dict[str, Any] | None) -> str:
        if not obj:
            return ""
        return "\n".join(f"{k}={obj[k]}" for k in sorted(obj))

    fields = [
        "GRAPHRUN.RUN.v1",
        run["run_id"],
        run["experiment_id"],
        run["graph_id"],
        run["started_at"],
        sorted_kv(run.get("parameters")),
        sorted_kv(run.get("tags")),
    ]
    return sha256_hex(frame(fields))


def callback_digest(callback: dict[str, Any]) -> str:
    scalars = {}
    for key in (
        "event_id",
        "run_id",
        "experiment_id",
        "graph_digest",
        "policy_version",
        "schema_version",
        "status",
        "occurred_at",
        "artifact_digest",
    ):
        if key in callback and callback[key] is not None:
            scalars[key] = str(callback[key])
    fields = ["GRAPHRUN.CALLBACK.v1"]
    for key in sorted(scalars):
        fields.append(f"{key}={scalars[key]}")
    metrics = callback.get("metrics") or {}
    metric_lines = []
    for name in sorted(metrics):
        value = metrics[name]
        if isinstance(value, (int, float, Decimal)):
            rendered = format(Decimal(str(value)).normalize(), "f").rstrip("0").rstrip(".") or "0"
        else:
            rendered = str(value)
        metric_lines.append(f"metrics.{name}={rendered}")
    fields.extend(sorted(metric_lines))
    return sha256_hex(frame(fields))


def attestation_payload_bytes(
    policy_commit_id: str,
    policy_digest: str,
    mlflow_sha: str,
    schema_sha: str,
    graph_sha: str,
    run_sha: str,
    callback_sha: str,
    key_id: str,
    attestation_schema_version: str = "1",
) -> bytes:
    return frame(
        [
            "GRAPHRUN.ATTEST.v1",
            policy_commit_id,
            policy_digest,
            mlflow_sha,
            schema_sha,
            graph_sha,
            run_sha,
            callback_sha,
            key_id,
            attestation_schema_version,
        ]
    )


def generate_ed25519_keypair(directory: Path, name: str) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    private = Ed25519PrivateKey.generate()
    pk8 = directory / f"{name}.pk8"
    pub = directory / f"{name}.pub"
    pk8.write_bytes(
        private.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
    )
    pub.write_bytes(
        private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    )
    pk8.chmod(0o600)
    return pk8, pub


def wait_http(url: str, timeout: float = 45.0) -> None:
    import urllib.error
    import urllib.request

    deadline = time.time() + timeout
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if 200 <= resp.status < 500:
                    return
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(0.4)
    raise TimeoutError(f"service not ready: {url} last={last_err}")


def stop_signer() -> None:
    """Stop a healthy GraphRunSigner JVM so in-memory identity state cannot leak across probes."""
    state_dir = Path("/tmp/graphrun-signer")
    pid_file = state_dir / "graph-run-signer.pid"
    if not pid_file.is_file():
        return
    try:
        pid = int(pid_file.read_text().strip())
    except ValueError:
        pid_file.unlink(missing_ok=True)
        return
    subprocess.run(["kill", str(pid)], check=False, capture_output=True, text=True)
    deadline = time.time() + 10.0
    while time.time() < deadline:
        alive = subprocess.run(
            ["kill", "-0", str(pid)],
            check=False,
            capture_output=True,
            text=True,
        )
        if alive.returncode != 0:
            break
        time.sleep(0.2)
    else:
        subprocess.run(["kill", "-9", str(pid)], check=False, capture_output=True, text=True)
    pid_file.unlink(missing_ok=True)


def ensure_fresh_signer(*, clear_log: bool = False) -> None:
    """Kill any prior signer JVM, optionally truncate its log, then start a clean process."""
    stop_signer()
    log_path = Path("/tmp/graphrun-signer/graph-run-signer.log")
    if clear_log and log_path.is_file():
        log_path.write_text("")
    run_cmd([str(SCRIPTS / "start-pkg.sh")], check=False)
    wait_http("http://127.0.0.1:18082/health")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def seed_gradle_home(target: Path) -> None:
    template = Path(os.environ.get("GRADLE_CACHE_TEMPLATE", "/opt/gradle-cache-template"))
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    if template.is_dir():
        shutil.copytree(template, target, dirs_exist_ok=True)


def run_cmd(args: list[str], env: dict[str, str] | None = None, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        env=merged,
        text=True,
        capture_output=True,
        check=check,
    )
