"""Behavioral verification for the commissioned local relay generation."""
from __future__ import annotations

import hashlib
import json
import socket
import sqlite3
import stat
import subprocess
import time
from pathlib import Path

APP = Path("/app")
CONFIG_DIR = APP / "etc/harbor-relay"
AUDIT = APP / "var/deployment-audit.db"
MANIFEST = APP / "var/deployment-manifest.json"
LOCK = APP / "var/harbor-deployment.lock"
ZERO = "0" * 64

# The arrival replay fixture is intentionally pinned to the canonical bytes used by
# the sealed request corpus. Keep this explicit pin synchronized with the packaged file.
ARRIVAL_REPLAY_SHA256 = "4c9841e467bc1842aa5beb3992543e9f6c7114168fc4196692911980abd69237"

PROTECTED = {
    "docs/audit-database-contract.md": "6a69e8976bc4d1d4c69b53f61ddf1c90d46e236709f518bb000c176d7d9a2f5a",
    "docs/capacity-and-payload-notes.md": "78fea40500906017363413cc407b158f9639f5bced544b031e678133a07f00e1",
    "docs/catalog-field-notes.md": "1cfe0a8a61bfe73ad5d81685661bfca1ce8113e7ff3821e1edbb87b887ad98de",
    "docs/oncall-shift-notes.md": "b9759f083a19489997c3957cead3d3fb0b8187626599c6a31ce8f02e3693827f",
    "docs/operator-commissioning-contract.md": "cb33d8e9c528417de1ab54d92bb25ab87457d7f8c1d4bf662f3a4e3d99d565da",
    "docs/publication-and-audit-minutes.md": "f224593ec58eeaa72b3f2e06f0af455df3672eab703c65b7946fa3e063146c7a",
    "docs/publication-state-machine.md": "7caa0a2f94669e5adb1313cde280bda1dd349105e8436ea5d63d5f1143c41ae9",
    "docs/service-commissioning-corpus.manifest": "30a934ec236544a1eb02e92569b8839e773317fd35faa917ff0651191f67ada0",
    "docs/relay-config-format.md": "379a52dcc094b133f583c67afd3b7eb48b35d6417b66fed7e6a081f1df57b000",
    "docs/relay-operations-handbook.md": "68ec339d7842c525ecd52caaa27b6ffbc342e10cdc9fa29573fc564135323113",
    "docs/route-governance-record.md": "fd7f57e4f6f3cba632d52099300042aa293d4efc20b264ca4d085ccdb754c4f7",
    "docs/socket-evidence-review.md": "dce8576d9f1949c7bf4a3b580ac1a7ee0074c68ba30b3a27d336c782bca26f10",
    "etc/harbor-relay/environment": "37a348b1f87129d1798bf70fbc27a7b3ac19f86d1fed568760b4527d5e4b2ac8",
    "etc/harbor-relay/service.account": "347b74cca9e03f1d208e1b5c7026830abd046a38d16411a14dfb8b46d6e361bf",
    "evidence/capture.meta": "56334ed560725dc8a3bc8e7c621b7b0da08d6f36a4cff774069481e61d7140ae",
    "evidence/relay.lsof": "c011e2763c5a4b16333358e337d217bbaaa9b195bda4a00df3ae3a33bb6b89f1",
    "evidence/relay.strace": "9221acfe033c3079863ef635eb772a67f5fc8f4852ad285ebb42078699681a11",
    "fixtures/README.txt": "da120e89b13e5b27b3519860c0cfd59e178ebff7709411aab430c56f5dbdce2f",
    "fixtures/bootstrap-config/limits.conf": "f28a35039bff7cae9ceb372296939043a89fd08072baa8bf5ff71e8725d60af1",
    "fixtures/bootstrap-config/relay.conf": "1aafa548b85f221e911ee4a6df4388e24d980ec1f07f60e47fa63793d2ec5169",
    "fixtures/bootstrap-config/routes.map": "65dad79e3b2217a5c34e9fbac418bd720514526bdebe154e7a5397fa35a63381",
    "fixtures/requests/arrival-replay.http": ARRIVAL_REPLAY_SHA256,
    "fixtures/requests/manifest-replay.http": "ad3a76dd6c30f1127181a3d119d0d5456b21d3db71100d62e448373e1d88aec9",
    "fixtures/requests/replay-set.manifest": "68bbcc614bb582f239338cd0bb11d2f7e0c3bb02f02bcf2d5f3c7ab229101a66",
    "fixtures/requests/status-replay.http": "96f0bdf0e942f7ed65512d8762ca7610c3ee2cf09ab964af576b7e1aab0acef9",
    "scripts/initialize-service-state": "194aa338b81efd7ab956ec6c5fba19d6a2225ab82ba35bd505b85a956d57e5a6",
    "scripts/send-sample-request": "6b55e5deba6ed58ee8b9d71dbd3b019bede64a62c2ce9f3fc70daa8698c48f9b",
    "share/deployment-catalog.batch": "4fc9b616e2541e785b7172367fff16aa31d8d18cbb5583b3689e1636405c4b59",
}

EXPECTED_RELAY = {
    "site_key": "st-042",
    "socket_path": "/app/run/harbor-relay/recovery.sock",
    "socket_mode": "0660",
    "socket_owner": "relayops",
    "socket_group": "relay",
    "listen_backlog": "128",
    "route_map": "/app/etc/harbor-relay/routes.map",
    "limits_file": "/app/etc/harbor-relay/limits.conf",
    "audit_db": "/app/var/deployment-audit.db",
    "catalog_generation": "29",
}
EXPECTED_LIMITS = {
    "open_files_soft": "640",
    "reserved_files": "64",
    "max_connections": "108",
    "request_body_limit": "65536",
}
EXPECTED_ROUTES = [
    ("GET", "/v1/berth/capabilities", "http://127.0.0.1:5902/capabilities", "preserve", "1200", "rt-203"),
    ("GET", "/v1/berth/status", "http://127.0.0.1:5902/status", "preserve", "725", "rt-200"),
    ("POST", "/v1/berth/arrivals", "http://127.0.0.1:5901/intake/arrivals-v2", "custody-token", "1850", "rt-201"),
    ("POST", "/v1/berth/manifest", "http://127.0.0.1:5901/intake/manifest-v2", "dual-proof", "4100", "rt-204"),
]


def sha256(path: Path) -> str:
    """Return the lowercase SHA-256 digest of one file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest_lines(values: list[str]) -> str:
    """Hash newline-terminated digest lines using the publication contract."""
    return hashlib.sha256(("\n".join(values) + "\n").encode()).hexdigest()


def read_key_values(path: Path) -> dict[str, str]:
    """Read an ordered key/value configuration into a dictionary."""
    return dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines())


def catalog_output() -> bytes:
    """Obtain the sealed catalog through the same public batch interface available to operators."""
    result = subprocess.run(
        [str(APP / "bin/catalog-query"), "--batch-file", str(APP / "share/deployment-catalog.batch")],
        check=True,
        capture_output=True,
    )
    return result.stdout


def send_unix(socket_path: Path, request: bytes) -> tuple[bytes, bytes]:
    """Send one HTTP message to the relay over its Unix socket."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(str(socket_path))
        client.sendall(request)
        client.shutdown(socket.SHUT_WR)
        response = bytearray()
        while True:
            chunk = client.recv(65536)
            if not chunk:
                break
            response.extend(chunk)
    head, body = bytes(response).split(b"\r\n\r\n", 1)
    return head, body


def test_authoritative_commissioning_inputs_are_unchanged() -> None:
    """Verify the policy corpus, operating records, fixtures, interface, and initialization assets remain immutable."""
    for relative, expected in PROTECTED.items():
        path = APP / relative
        assert path.is_file(), relative
        assert sha256(path) == expected, relative
    manifest = (APP / "docs/service-commissioning-corpus.manifest").read_text(encoding="utf-8").splitlines()
    listed = [line.split("\t")[1] for line in manifest if line and not line.startswith("#")]
    assert listed == [
        "relay-operations-handbook.md",
        "socket-evidence-review.md",
        "route-governance-record.md",
        "capacity-and-payload-notes.md",
        "publication-and-audit-minutes.md",
    ]


def test_catalog_interface_and_platform_binaries_remain_valid() -> None:
    """Verify the sealed catalog generation and existing relay binaries remain usable without source rebuilding."""
    with sqlite3.connect("file:/opt/harbor/operations.db?mode=ro", uri=True) as db:
        tables = [
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        logical = {}
        for table in tables:
            columns = [row[1] for row in db.execute(f"PRAGMA table_info({table})")]
            order = ",".join(str(index + 1) for index in range(len(columns)))
            rows = [list(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY {order}")]
            logical[table] = {"columns": columns, "rows": rows}
        encoded = json.dumps(logical, separators=(",", ":"), sort_keys=True).encode()
        assert hashlib.sha256(encoded).hexdigest() == "257aeb2867adb97ba5ad8d47ae3fbfe678ba965236d5998616314db99a9e3780"
    output = catalog_output().decode("utf-8")
    assert output.startswith("@result catalog_meta\n")
    assert output.rstrip().endswith("@end")
    check = subprocess.run(
        [str(APP / "bin/harbor-relay"), "--check-config", str(CONFIG_DIR / "relay.conf")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert check.returncode == 0, check.stderr
    for forbidden in [APP / "src", APP / "include", APP / "Makefile", APP / "build"]:
        assert not forbidden.exists()


def test_commissioned_configuration_matches_authorized_socket_routes_and_limits() -> None:
    """Verify the installed text configuration contains the chronology-safe socket, closed routes, and calculated limits."""
    relay_path = CONFIG_DIR / "relay.conf"
    limits_path = CONFIG_DIR / "limits.conf"
    routes_path = CONFIG_DIR / "routes.map"
    assert read_key_values(relay_path) == EXPECTED_RELAY
    assert read_key_values(limits_path) == EXPECTED_LIMITS
    route_lines = routes_path.read_text(encoding="utf-8").splitlines()
    assert route_lines[0] == "method\texternal_path\tupstream\tauth_mode\ttimeout_ms\tsource_route_id"
    assert [tuple(line.split("\t")) for line in route_lines[1:]] == EXPECTED_ROUTES
    assert relay_path.read_bytes().endswith(b"\n")
    assert limits_path.read_bytes().endswith(b"\n")
    assert routes_path.read_bytes().endswith(b"\n")
    assert "data-plane.sock\"" in (APP / "evidence/relay.strace").read_text() and "EACCES" in (APP / "evidence/relay.strace").read_text()
    after = (APP / "evidence/relay.lsof").read_text().split("# snapshot=after", 1)[1]
    assert EXPECTED_RELAY["socket_path"] not in after


def test_service_generation_permissions_and_clean_state_are_correct() -> None:
    """Verify only the documented service-generation files remain, with required modes and no staging or compiler residue."""
    expected_modes = {
        CONFIG_DIR / "relay.conf": 0o640,
        CONFIG_DIR / "limits.conf": 0o640,
        CONFIG_DIR / "routes.map": 0o640,
        AUDIT: 0o600,
        MANIFEST: 0o640,
        LOCK: 0o600,
    }
    for path, mode in expected_modes.items():
        assert path.is_file(), path
        assert stat.S_IMODE(path.stat().st_mode) == mode
    residue = []
    for directory in [CONFIG_DIR, APP / "var"]:
        residue.extend(
            path
            for path in directory.iterdir()
            if any(token in path.name for token in (".tmp", ".bak", "-journal", "-wal", "-shm"))
        )
    assert residue == []


def test_deployment_manifest_has_deterministic_identity_and_exact_provenance() -> None:
    """Verify the compact JSON manifest identity, ordering, provenance hashes, and publication metadata independently."""
    raw = MANIFEST.read_text(encoding="utf-8")
    manifest = json.loads(raw)
    assert raw == json.dumps(manifest, separators=(",", ":")) + "\n"
    assert list(manifest) == [
        "run_id",
        "site_key",
        "handbook_revision",
        "catalog_generation",
        "configuration",
        "routes",
        "assertions",
        "inputs",
        "publication",
    ]
    assert manifest["site_key"] == "st-042"
    assert manifest["handbook_revision"] == "HRH-2026.07-R11"
    assert manifest["catalog_generation"] == 29
    expected_configuration = {**EXPECTED_RELAY, **EXPECTED_LIMITS}
    assert manifest["configuration"] == expected_configuration
    assert [tuple(str(item[key]) for key in ("method", "external_path", "upstream", "auth_mode", "timeout_ms", "source_route_id")) for item in manifest["routes"]] == EXPECTED_ROUTES
    assert [item["decision_code"] for item in manifest["routes"]] == ["required", "selected", "selected", "replaced"]
    assert len(manifest["assertions"]) == 10 and all(item["passed"] == 1 for item in manifest["assertions"])
    assert [item["kind"] for item in manifest["inputs"]] == sorted(item["kind"] for item in manifest["inputs"])

    request_paths = [APP / "fixtures/requests/replay-set.manifest"]
    for line in request_paths[0].read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            request_paths.append(Path(line.split("\t", 1)[1]))
    request_set = digest_lines([sha256(path) for path in request_paths])
    evidence_set = digest_lines([sha256(APP / "evidence/capture.meta"), sha256(APP / "evidence/relay.strace"), sha256(APP / "evidence/relay.lsof")])
    catalog_sha = hashlib.sha256(catalog_output()).hexdigest()
    seed = "|".join(
        [
            "st-042",
            "HRH-2026.07-R11",
            "29",
            request_set,
            evidence_set,
            catalog_sha,
            sha256(CONFIG_DIR / "relay.conf"),
            sha256(CONFIG_DIR / "limits.conf"),
            sha256(CONFIG_DIR / "routes.map"),
        ]
    )
    assert manifest["run_id"] == hashlib.sha256(seed.encode()).hexdigest()[:24]

    input_rows = {(item["kind"], item["path"]): item for item in manifest["inputs"]}
    catalog_item = input_rows[("catalog-batch-result", "/app/share/deployment-catalog.batch")]
    assert catalog_item["sha256"] == catalog_sha
    assert catalog_item["bytes"] == len(catalog_output())
    for (kind, path_text), item in input_rows.items():
        if kind == "catalog-batch-result":
            continue
        path = Path(path_text)
        assert item["sha256"] == sha256(path)
        assert item["bytes"] == path.stat().st_size

    expected_publication = [
        (CONFIG_DIR / "relay.conf", "0640"),
        (CONFIG_DIR / "limits.conf", "0640"),
        (CONFIG_DIR / "routes.map", "0640"),
        (AUDIT, "0600"),
        (MANIFEST, "0640"),
    ]
    assert [item["path"] for item in manifest["publication"]] == [str(path) for path, _ in expected_publication]
    for item, (path, mode) in zip(manifest["publication"], expected_publication, strict=True):
        assert item["mode"] == mode
        if path in {AUDIT, MANIFEST}:
            assert (item["sha256"], item["bytes"]) == (ZERO, 0)
        else:
            assert (item["sha256"], item["bytes"]) == (sha256(path), path.stat().st_size)


def test_deployment_audit_schema_constraints_and_reconciliation_are_complete() -> None:
    """Verify the seven-table deployment audit is constrained, complete, and reconciled with all publication bytes and decisions."""
    with sqlite3.connect(AUDIT) as db:
        assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY rowid")]
        assert tables == ["deployment_run", "input_artifact", "configuration", "route", "decision", "assertion", "publication_file"]
        run = db.execute(
            "SELECT run_id,site_key,handbook_revision,catalog_generation,status FROM deployment_run"
        ).fetchone()
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        assert run == (manifest["run_id"], "st-042", "HRH-2026.07-R11", 29, "commissioned")
        assert db.execute("SELECT COUNT(*) FROM assertion WHERE passed=1").fetchone() == (10,)
        assert db.execute("SELECT COUNT(*) FROM decision").fetchone() == (14,)
        assert [row[0] for row in db.execute("SELECT sequence FROM decision ORDER BY sequence")] == list(range(1, 15))
        assert db.execute("SELECT COUNT(*) FROM input_artifact").fetchone() == (8,)
        file_configuration = {**EXPECTED_RELAY, **EXPECTED_LIMITS}
        assert dict(db.execute("SELECT key,value FROM configuration")) == file_configuration
        audit_routes = db.execute(
            "SELECT method,external_path,upstream,auth_mode,timeout_ms,source_route_id FROM route ORDER BY method,external_path"
        ).fetchall()
        assert audit_routes == [row[:4] + (int(row[4]), row[5]) for row in EXPECTED_ROUTES]
        publication = {row[0]: row[1:] for row in db.execute("SELECT path,sha256,bytes,mode_text FROM publication_file")}
        assert publication[str(AUDIT)] == (ZERO, 0, "0600")
        assert publication[str(MANIFEST)] == (ZERO, 0, "0640")
        assert publication[str(CONFIG_DIR / "relay.conf")] == (sha256(CONFIG_DIR / "relay.conf"), (CONFIG_DIR / "relay.conf").stat().st_size, "0640")
    with sqlite3.connect(AUDIT) as db:
        for statement in (Path("/tests/deployment_assertions.sql").read_text(encoding="utf-8").split(";")):
            if statement.strip():
                assert db.execute(statement).fetchone() == (1,)


def test_commissioned_relay_serves_required_missing_and_oversized_requests() -> None:
    """Verify the existing relay binds the commissioned socket and serves all required HTTP outcomes."""
    socket_path = Path(EXPECTED_RELAY["socket_path"])
    socket_path.unlink(missing_ok=True)
    process = subprocess.Popen(
        [str(APP / "bin/harbor-relay")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.time() + 5
        while time.time() < deadline and not socket_path.exists() and process.poll() is None:
            time.sleep(0.05)
        assert socket_path.exists(), process.stderr.read() if process.stderr else "relay exited"
        expected = {
            "arrival": ("/v1/berth/arrivals", "rt-201"),
            "manifest": ("/v1/berth/manifest", "rt-204"),
            "status": ("/v1/berth/status", "rt-200"),
        }
        for line in (APP / "fixtures/requests/replay-set.manifest").read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            role, request_path = line.split("\t", 1)
            head, body = send_unix(socket_path, Path(request_path).read_bytes())
            payload = json.loads(body)
            assert b"200 OK" in head
            assert (payload["path"], payload["source_route_id"]) == expected[role]
        head, body = send_unix(socket_path, b"GET /v1/berth/capabilities?full=1 HTTP/1.1\r\nHost: x\r\n\r\n")
        assert b"200 OK" in head and json.loads(body)["source_route_id"] == "rt-203"
        head, _ = send_unix(socket_path, b"GET /not-present HTTP/1.1\r\nHost: x\r\n\r\n")
        assert b"404 Not Found" in head
        oversized = b"x" * 65537
        request = b"POST /v1/berth/arrivals HTTP/1.1\r\nHost: x\r\nContent-Length: 65537\r\n\r\n" + oversized
        head, _ = send_unix(socket_path, request)
        assert b"413 Payload Too Large" in head
        unix_rows = Path("/proc/net/unix").read_text(encoding="utf-8")
        assert str(socket_path) in unix_rows
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        socket_path.unlink(missing_ok=True)
