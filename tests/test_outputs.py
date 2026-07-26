"""Behavioral verification for the authorized local relay generation."""
from __future__ import annotations

import hashlib
import json
import os
import socket
import sqlite3
import stat
import subprocess
import time
from pathlib import Path

APP = Path("/app")
CONFIG_DIR = APP / "etc/harbor-relay"
ACTIVATION = APP / "var/activation-seal.json"
AUDIT = APP / "var/deployment-audit.db"
MANIFEST = APP / "var/deployment-manifest.json"
LOCK = APP / "var/harbor-deployment.lock"
ZERO = "0" * 64

PROTECTED: dict[str, str] = {
    "docs/audit-database-contract.md": "948100ac7ee6035375d5731478e3cc183ed577823c38b46c0fd21e9b54174500",
    "docs/capacity-and-payload-notes.md": "5e3cc03e3f27d272a10acc07909017e8de00c428669e3120a2281f52c55ef562",
    "docs/catalog-field-notes.md": "1cfe0a8a61bfe73ad5d81685661bfca1ce8113e7ff3821e1edbb87b887ad98de",
    "docs/change-control-governance.md": "960291938febeda1bb045c3b15ca42598915bf26e7ca05eaa8124fe12a10630f",
    "docs/oncall-shift-notes.md": "b9759f083a19489997c3957cead3d3fb0b8187626599c6a31ce8f02e3693827f",
    "docs/operator-commissioning-contract.md": "deefc74d3e32cc3fe3afcfeea80900df42b5cd0664f149be38273373018dfaaf",
    "docs/publication-and-audit-minutes.md": "f224593ec58eeaa72b3f2e06f0af455df3672eab703c65b7946fa3e063146c7a",
    "docs/publication-state-machine.md": "7caa0a2f94669e5adb1313cde280bda1dd349105e8436ea5d63d5f1143c41ae9",
    "docs/service-commissioning-corpus.manifest": "aca90702a3e14a61d1a7092ee4f9fc52bec8499aa3da1f7f1837173c48be14ae",
    "docs/relay-config-format.md": "89fbb76c368fd0336442d95b59a1c5256f14027fb520a37faac2349dc71714bb",
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
    "fixtures/requests/arrival-replay.http": "4c9841e467bc1842aa5beb3992543e9f6c7114168fc4196692911980abd69237",
    "fixtures/requests/manifest-replay.http": "ad3a76dd6c30f1127181a3d119d0d5456b21d3db71100d62e448373e1d88aec9",
    "fixtures/requests/replay-set.manifest": "68bbcc614bb582f239338cd0bb11d2f7e0c3bb02f02bcf2d5f3c7ab229101a66",
    "fixtures/requests/status-replay.http": "96f0bdf0e942f7ed65512d8762ca7610c3ee2cf09ab964af576b7e1aab0acef9",
    "scripts/initialize-service-state": "714cc1811c16598c6d0d8bb24ce0f58be42e0eb87f6a6d161a8c092d209105e2",
    "scripts/send-sample-request": "6b55e5deba6ed58ee8b9d71dbd3b019bede64a62c2ce9f3fc70daa8698c48f9b",
    "share/deployment-catalog.batch": "4fc9b616e2541e785b7172367fff16aa31d8d18cbb5583b3689e1636405c4b59",
    "share/change-control.batch": "59498d7e6d7e35b5d1f2929a1fbd9b8960f2628ed5dc26b5fee818d18da585a8",
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
    (
        "GET",
        "/v1/berth/capabilities",
        "http://127.0.0.1:5902/capabilities",
        "preserve",
        "1200",
        "rt-203",
    ),
    ("GET", "/v1/berth/status", "http://127.0.0.1:5902/status", "preserve", "725", "rt-200"),
    (
        "POST",
        "/v1/berth/arrivals",
        "http://127.0.0.1:5901/intake/arrivals-v2",
        "custody-token",
        "1850",
        "rt-201",
    ),
    (
        "POST",
        "/v1/berth/manifest",
        "http://127.0.0.1:5901/intake/manifest-v2",
        "dual-proof",
        "4100",
        "rt-204",
    ),
]
EXPECTED_APPROVALS = [
    {
        "exclusive_group": "operations",
        "approver_id": "alice.ops",
        "role_code": "OPS",
        "weight": 2,
        "state": "approve",
        "event_id": "ev-a1",
    },
    {
        "exclusive_group": "security",
        "approver_id": "bob.sec",
        "role_code": "SECURITY",
        "weight": 2,
        "state": "reinstate",
        "event_id": "ev-b3",
    },
]


def sha256(path: Path) -> str:
    """Return the lowercase SHA-256 digest of one file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest_lines(values: list[str]) -> str:
    """Hash newline-terminated digest lines using the publication contract."""
    return hashlib.sha256(("\n".join(values) + "\n").encode()).hexdigest()


def read_key_values(path: Path) -> dict[str, str]:
    """Read a key/value configuration into a dictionary."""
    return dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines())


def query_catalog(database: Path, batch: Path) -> bytes:
    """Capture one read-only catalog snapshot through the public interface."""
    environment = os.environ.copy()
    if database.name == "change-control.db":
        environment["HARBOR_CATALOG_DB"] = str(database)
    else:
        environment.pop("HARBOR_CATALOG_DB", None)
    result = subprocess.run(
        [str(APP / "bin/catalog-query"), "--batch-file", str(batch)],
        check=True,
        capture_output=True,
        env=environment,
    )
    return result.stdout


def logical_database_digest(path: Path) -> str:
    """Return a deterministic digest of all logical user tables in a SQLite catalog."""
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as database:
        tables = [
            row[0]
            for row in database.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        logical = {}
        for table in tables:
            columns = [row[1] for row in database.execute(f"PRAGMA table_info({table})")]
            order = ",".join(str(index + 1) for index in range(len(columns)))
            rows = [list(row) for row in database.execute(f"SELECT * FROM {table} ORDER BY {order}")]
            logical[table] = {"columns": columns, "rows": rows}
    encoded = json.dumps(logical, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


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
    """Verify all policy, evidence, catalog-interface, and initialization assets remain immutable."""
    for relative, expected in PROTECTED.items():
        path = APP / relative
        assert path.is_file(), relative
        assert sha256(path) == expected, relative
    lines = (APP / "docs/service-commissioning-corpus.manifest").read_text(encoding="utf-8").splitlines()
    listed = [line.split("\t")[1] for line in lines if line and not line.startswith("#")]
    assert listed == [
        "relay-operations-handbook.md",
        "socket-evidence-review.md",
        "route-governance-record.md",
        "capacity-and-payload-notes.md",
        "change-control-governance.md",
        "publication-and-audit-minutes.md",
    ]


def test_catalog_interfaces_and_platform_binaries_remain_valid() -> None:
    """Verify both sealed catalogs and existing relay binaries remain usable without rebuilding source."""
    assert logical_database_digest(Path("/opt/harbor/operations.db")) == "257aeb2867adb97ba5ad8d47ae3fbfe678ba965236d5998616314db99a9e3780"
    assert logical_database_digest(Path("/opt/harbor/change-control.db")) == "c0c1aaa5e488d0a0da8cb5a16ec2024f9a95ccc9df1254426cc41efb46f5d552"
    operations = query_catalog(Path("/opt/harbor/operations.db"), APP / "share/deployment-catalog.batch")
    changes = query_catalog(Path("/opt/harbor/change-control.db"), APP / "share/change-control.batch")
    assert operations.startswith(b"@result catalog_meta\n") and operations.rstrip().endswith(b"@end")
    assert changes.startswith(b"@result change_meta\n") and changes.rstrip().endswith(b"@end")
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
    """Verify the installed text configuration contains the authorized socket, routes, and limits."""
    relay_path = CONFIG_DIR / "relay.conf"
    limits_path = CONFIG_DIR / "limits.conf"
    routes_path = CONFIG_DIR / "routes.map"
    assert read_key_values(relay_path) == EXPECTED_RELAY
    assert read_key_values(limits_path) == EXPECTED_LIMITS
    route_lines = routes_path.read_text(encoding="utf-8").splitlines()
    assert route_lines[0] == "method\texternal_path\tupstream\tauth_mode\ttimeout_ms\tsource_route_id"
    assert [tuple(line.split("\t")) for line in route_lines[1:]] == EXPECTED_ROUTES
    assert all(path.read_bytes().endswith(b"\n") for path in [relay_path, limits_path, routes_path])
    trace = (APP / "evidence/relay.strace").read_text(encoding="utf-8")
    assert "data-plane.sock\"" in trace and "EACCES" in trace
    after = (APP / "evidence/relay.lsof").read_text(encoding="utf-8").split("# snapshot=after", 1)[1]
    assert EXPECTED_RELAY["socket_path"] not in after


def test_activation_seal_reconciles_ticket_quorum_candidate_and_identity() -> None:
    """Verify temporal ticket selection, effective approval quorum, activation choice, and seal identity."""
    raw = ACTIVATION.read_text(encoding="utf-8")
    seal = json.loads(raw)
    assert raw == json.dumps(seal, separators=(",", ":")) + "\n"
    assert list(seal) == [
        "ticket_id",
        "change_generation",
        "activation_id",
        "release_lane",
        "quorum_required",
        "quorum_observed",
        "approvals",
        "authorization_digest",
        "activation_token",
    ]
    assert seal["ticket_id"] == "chg-2026-071"
    assert seal["change_generation"] == 11
    assert seal["activation_id"] == "act-071-recovery-b4"
    assert seal["release_lane"] == "BLUE"
    assert (seal["quorum_required"], seal["quorum_observed"]) == (4, 4)
    assert seal["approvals"] == EXPECTED_APPROVALS
    member_lines = [
        "|".join(
            [
                item["exclusive_group"],
                item["approver_id"],
                item["role_code"],
                str(item["weight"]),
                item["state"],
                item["event_id"],
            ]
        )
        for item in EXPECTED_APPROVALS
    ]
    assert seal["authorization_digest"] == digest_lines(member_lines)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    token_seed = "|".join(
        [seal["ticket_id"], seal["activation_id"], seal["authorization_digest"], manifest["run_id"]]
    )
    assert seal["activation_token"] == hashlib.sha256(token_seed.encode()).hexdigest()[:24]
    assert manifest["authorization"] == seal


def test_service_generation_permissions_and_clean_state_are_correct() -> None:
    """Verify all documented generation files have required modes and no prohibited residue remains."""
    expected_modes = {
        CONFIG_DIR / "relay.conf": 0o640,
        CONFIG_DIR / "limits.conf": 0o640,
        CONFIG_DIR / "routes.map": 0o640,
        ACTIVATION: 0o640,
        AUDIT: 0o600,
        MANIFEST: 0o640,
        LOCK: 0o600,
    }
    for path, mode in expected_modes.items():
        assert path.is_file(), path
        assert stat.S_IMODE(path.stat().st_mode) == mode
    assert LOCK.stat().st_size == 0
    residue = []
    for directory in [CONFIG_DIR, APP / "var"]:
        residue.extend(
            path
            for path in directory.iterdir()
            if any(token in path.name for token in (".tmp", ".bak", "-journal", "-wal", "-shm"))
        )
    assert residue == []


def test_deployment_manifest_has_deterministic_identity_and_exact_provenance() -> None:
    """Verify compact manifest identity, ordering, two-catalog provenance, and publication metadata."""
    raw = MANIFEST.read_text(encoding="utf-8")
    manifest = json.loads(raw)
    assert raw == json.dumps(manifest, separators=(",", ":")) + "\n"
    assert list(manifest) == [
        "run_id",
        "site_key",
        "handbook_revision",
        "catalog_generation",
        "change_generation",
        "configuration",
        "routes",
        "assertions",
        "authorization",
        "inputs",
        "publication",
    ]
    assert manifest["site_key"] == "st-042"
    assert manifest["handbook_revision"] == "HRH-2026.07-R11"
    assert (manifest["catalog_generation"], manifest["change_generation"]) == (29, 11)
    assert manifest["configuration"] == {**EXPECTED_RELAY, **EXPECTED_LIMITS}
    actual_routes = [
        tuple(
            str(item[key])
            for key in ("method", "external_path", "upstream", "auth_mode", "timeout_ms", "source_route_id")
        )
        for item in manifest["routes"]
    ]
    assert actual_routes == EXPECTED_ROUTES
    assert [item["decision_code"] for item in manifest["routes"]] == [
        "required",
        "selected",
        "selected",
        "replaced",
    ]
    assert len(manifest["assertions"]) == 15 and all(item["passed"] == 1 for item in manifest["assertions"])
    assert [item["kind"] for item in manifest["inputs"]] == sorted(item["kind"] for item in manifest["inputs"])

    request_paths = [APP / "fixtures/requests/replay-set.manifest"]
    for line in request_paths[0].read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            request_paths.append(Path(line.split("\t", 1)[1]))
    request_set = digest_lines([sha256(path) for path in request_paths])
    evidence_set = digest_lines(
        [
            sha256(APP / "evidence/capture.meta"),
            sha256(APP / "evidence/relay.strace"),
            sha256(APP / "evidence/relay.lsof"),
        ]
    )
    operations_snapshot = query_catalog(
        Path("/opt/harbor/operations.db"), APP / "share/deployment-catalog.batch"
    )
    change_snapshot = query_catalog(
        Path("/opt/harbor/change-control.db"), APP / "share/change-control.batch"
    )
    operations_sha = hashlib.sha256(operations_snapshot).hexdigest()
    change_sha = hashlib.sha256(change_snapshot).hexdigest()
    seed = "|".join(
        [
            "st-042",
            "HRH-2026.07-R11",
            "29",
            "11",
            request_set,
            evidence_set,
            operations_sha,
            change_sha,
            manifest["authorization"]["authorization_digest"],
            sha256(CONFIG_DIR / "relay.conf"),
            sha256(CONFIG_DIR / "limits.conf"),
            sha256(CONFIG_DIR / "routes.map"),
        ]
    )
    assert manifest["run_id"] == hashlib.sha256(seed.encode()).hexdigest()[:24]

    inputs = {(item["kind"], item["path"]): item for item in manifest["inputs"]}
    operations_item = inputs[("catalog-batch-result", "/app/share/deployment-catalog.batch")]
    change_item = inputs[("change-catalog-batch-result", "/app/share/change-control.batch")]
    assert (operations_item["sha256"], operations_item["bytes"]) == (
        operations_sha,
        len(operations_snapshot),
    )
    assert (change_item["sha256"], change_item["bytes"]) == (change_sha, len(change_snapshot))
    for (kind, path_text), item in inputs.items():
        if kind.endswith("catalog-batch-result"):
            continue
        path = Path(path_text)
        assert (item["sha256"], item["bytes"]) == (sha256(path), path.stat().st_size)

    expected_publication = [
        (CONFIG_DIR / "relay.conf", "0640"),
        (CONFIG_DIR / "limits.conf", "0640"),
        (CONFIG_DIR / "routes.map", "0640"),
        (ACTIVATION, "0640"),
        (AUDIT, "0600"),
        (MANIFEST, "0640"),
    ]
    assert [item["path"] for item in manifest["publication"]] == [
        str(path) for path, _ in expected_publication
    ]
    for item, (path, mode) in zip(manifest["publication"], expected_publication, strict=True):
        assert item["mode"] == mode
        if path in {AUDIT, MANIFEST}:
            assert (item["sha256"], item["bytes"]) == (ZERO, 0)
        else:
            assert (item["sha256"], item["bytes"]) == (sha256(path), path.stat().st_size)


def test_deployment_audit_schema_constraints_and_reconciliation_are_complete() -> None:
    """Verify the nine-table audit, twenty decisions, two approvals, and all publication bytes."""
    with sqlite3.connect(AUDIT) as database:
        assert database.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        tables = [
            row[0]
            for row in database.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY rowid")
        ]
        assert tables == [
            "deployment_run",
            "input_artifact",
            "configuration",
            "route",
            "decision",
            "assertion",
            "authorization",
            "approval",
            "publication_file",
        ]
        run = database.execute(
            "SELECT run_id,site_key,handbook_revision,catalog_generation,change_generation,status "
            "FROM deployment_run"
        ).fetchone()
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        assert run == (manifest["run_id"], "st-042", "HRH-2026.07-R11", 29, 11, "commissioned")
        assert database.execute("SELECT COUNT(*) FROM assertion WHERE passed=1").fetchone() == (15,)
        assert database.execute("SELECT COUNT(*) FROM decision").fetchone() == (20,)
        assert [row[0] for row in database.execute("SELECT sequence FROM decision ORDER BY sequence")] == list(
            range(1, 21)
        )
        assert database.execute("SELECT COUNT(*) FROM input_artifact").fetchone() == (9,)
        assert dict(database.execute("SELECT key,value FROM configuration")) == {
            **EXPECTED_RELAY,
            **EXPECTED_LIMITS,
        }
        audit_routes = database.execute(
            "SELECT method,external_path,upstream,auth_mode,timeout_ms,source_route_id "
            "FROM route ORDER BY method,external_path"
        ).fetchall()
        assert audit_routes == [row[:4] + (int(row[4]), row[5]) for row in EXPECTED_ROUTES]
        authorization = database.execute(
            "SELECT ticket_id,change_generation,activation_id,release_lane,quorum_required,"
            "quorum_observed,authorization_digest,activation_token FROM authorization"
        ).fetchone()
        seal = json.loads(ACTIVATION.read_text(encoding="utf-8"))
        assert authorization == (
            seal["ticket_id"],
            11,
            seal["activation_id"],
            seal["release_lane"],
            4,
            4,
            seal["authorization_digest"],
            seal["activation_token"],
        )
        approval_rows = database.execute(
            "SELECT exclusive_group,approver_id,role_code,weight,state,event_id "
            "FROM approval ORDER BY exclusive_group,approver_id"
        ).fetchall()
        assert approval_rows == [
            tuple(item[key] for key in ("exclusive_group", "approver_id", "role_code", "weight", "state", "event_id"))
            for item in EXPECTED_APPROVALS
        ]
        publication = {
            row[0]: row[1:]
            for row in database.execute("SELECT path,sha256,bytes,mode_text FROM publication_file")
        }
        assert publication[str(ACTIVATION)] == (sha256(ACTIVATION), ACTIVATION.stat().st_size, "0640")
        assert publication[str(AUDIT)] == (ZERO, 0, "0600")
        assert publication[str(MANIFEST)] == (ZERO, 0, "0640")
        assert database.execute(
            "SELECT evidence FROM decision WHERE sequence=3 AND domain='socket'"
        ).fetchone() == ("last=EACCES",)
        assert database.execute(
            "SELECT subject,outcome FROM decision WHERE sequence=18 AND domain='change-control'"
        ).fetchone() == ("carol.sre", "rejected")
    with sqlite3.connect(AUDIT) as database:
        statements = Path("/tests/deployment_assertions.sql").read_text(encoding="utf-8").split(";")
        for statement in statements:
            if statement.strip():
                assert database.execute(statement).fetchone() == (1,)


def test_commissioned_relay_serves_required_missing_and_oversized_requests() -> None:
    """Verify the existing relay binds the socket and serves all required HTTP outcomes."""
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
        lines = (APP / "fixtures/requests/replay-set.manifest").read_text(encoding="utf-8").splitlines()
        for line in lines:
            if not line or line.startswith("#"):
                continue
            role, request_path = line.split("\t", 1)
            head, body = send_unix(socket_path, Path(request_path).read_bytes())
            payload = json.loads(body)
            assert b"200 OK" in head
            assert (payload["path"], payload["source_route_id"]) == expected[role]
        head, body = send_unix(
            socket_path,
            b"GET /v1/berth/capabilities?full=1 HTTP/1.1\r\nHost: x\r\n\r\n",
        )
        assert b"200 OK" in head and json.loads(body)["source_route_id"] == "rt-203"
        head, _ = send_unix(socket_path, b"GET /not-present HTTP/1.1\r\nHost: x\r\n\r\n")
        assert b"404 Not Found" in head
        oversized = b"x" * 65537
        request = (
            b"POST /v1/berth/arrivals HTTP/1.1\r\nHost: x\r\nContent-Length: 65537\r\n\r\n"
            + oversized
        )
        head, _ = send_unix(socket_path, request)
        assert b"413 Payload Too Large" in head
        assert str(socket_path) in Path("/proc/net/unix").read_text(encoding="utf-8")
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        socket_path.unlink(missing_ok=True)
