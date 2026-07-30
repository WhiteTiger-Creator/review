"""Behavioral verification for the commissioned local relay service."""
from __future__ import annotations

import grp
import hashlib
import json
import os
import pwd
import socket
import sqlite3
import stat
import subprocess
import time
from pathlib import Path

APP = Path("/app")
CONFIG_DIR = APP / "etc/harbor-relay"
WINDOW_PLAN = APP / "var/window-plan.json"
AUDIT = APP / "var/commissioning-ledger.db"
MANIFEST = APP / "var/commissioning-manifest.json"
LOCK = APP / "var/harbor-commissioning.lock"
UNIT = Path("/etc/systemd/system/harbor-relay.service")
ZERO = "0" * 64

PROTECTED: dict[str, str] = {
    'docs/audit-database-contract.md': '44ba6db652ce6a883c552e51ac1c2871abaaa3d7521b4794d34423ebeb54bb3c',
    'docs/capacity-planning-notes.md': '46572e2269bbf98ea12d7d3b4603c72547f950ff4d3444ad7b61cbfb9bc27cf8',
    'docs/catalog-field-notes.md': 'c377749f7d2210b4e5ca8aa6435923d5538449289743569eba1e68690c562a70',
    'docs/commissioning-ledger-minutes.md': 'a7db8546f754f69903b1d1a823ac5032555b6242cf9b6312e9d2bc5b52305b80',
    'docs/maintenance-window-governance.md': 'fbeff0bedf1daa0e6b90d554fa350e7a9df34dbf875beb52364be7276e112b4f',
    'docs/oncall-shift-notes.md': '492e30d6b9a34f87fcf1998138515a34f90167c658d8b752ea7007c297285076',
    'docs/publication-state-machine.md': 'f6e9415ae84f20fb35ec3b4e17b675df36353b387d42d94fa7d4ed59d901d710',
    'docs/relay-config-format.md': '7d91cac9b7b1c8c57fc1e93a4e321489548fbf3c0c53697b407724b17450fef8',
    'docs/relay-operations-handbook.md': '53ec681552e4768da997b85f8e36dbc02237306a8f6ade686d14a7473ef54e05',
    'docs/route-allocation-register.md': '97400c92f3fd07a23de8573de6e35aca5a5a1deb4cc1e245a00845c5b6960f59',
    'docs/service-commissioning-contract.md': 'f8dbeeb9f8e667e04ecfa8f140f609f713e651ee750febc8b1cc8dff2488f3ba',
    'docs/service-commissioning-corpus.manifest': 'e1261cd9ea0c41d53972f73d21cfcd703dc5552b0b5df99933ad42d961698b05',
    'docs/socket-allocation-review.md': '6280d27a62fb4fe029cc474fc4aed18a503098d703fa95f1ea83774c17b15f16',
    'etc/harbor-relay/environment': '37a348b1f87129d1798bf70fbc27a7b3ac19f86d1fed568760b4527d5e4b2ac8',
    'etc/harbor-relay/service.account': '347b74cca9e03f1d208e1b5c7026830abd046a38d16411a14dfb8b46d6e361bf',
    'fixtures/README.txt': 'da120e89b13e5b27b3519860c0cfd59e178ebff7709411aab430c56f5dbdce2f',
    'fixtures/initial-config/limits.conf': 'f28a35039bff7cae9ceb372296939043a89fd08072baa8bf5ff71e8725d60af1',
    'fixtures/initial-config/relay.conf': '1aafa548b85f221e911ee4a6df4388e24d980ec1f07f60e47fa63793d2ec5169',
    'fixtures/initial-config/routes.map': '65dad79e3b2217a5c34e9fbac418bd720514526bdebe154e7a5397fa35a63381',
    'fixtures/requests/arrival-replay.http': '1952a39bd9edfe4868259d14675eb5219ef6f21afe4854ee3e91b0c8c4ea5795',
    'fixtures/requests/manifest-replay.http': 'ad3a76dd6c30f1127181a3d119d0d5456b21d3db71100d62e448373e1d88aec9',
    'fixtures/requests/replay-set.manifest': '68bbcc614bb582f239338cd0bb11d2f7e0c3bb02f02bcf2d5f3c7ab229101a66',
    'fixtures/requests/status-replay.http': '96f0bdf0e942f7ed65512d8762ca7610c3ee2cf09ab964af576b7e1aab0acef9',
    'records/socket-occupancy-snapshot.txt': 'bc2f1731dcfab37e1a957d8e15f846ec06886ec99c120ce62dd4b1274687004a',
    'records/socket-allocation-events.txt': '0810b4bfd6d7f5b1079c13960407bda1c04ec829c70760107ab460edc03e0384',
    'records/window.meta': '56334ed560725dc8a3bc8e7c621b7b0da08d6f36a4cff774069481e61d7140ae',
    'scripts/exercise-service': 'c55ead9e75e67e8339358969a5bbe7acdb690a29366e4dad46524aaaa6f6ae1f',
    'scripts/initialize-service-instance': 'f0df763120394a0417ffc62a70a0fde427ef97d5fb20729af6a2dac76ea596a9',
    'share/maintenance-window.batch': '01e52185a664069dbe2f471f9bf478bdc68b2957b72e886c45ecd890fa961fb7',
    'share/service-catalog.batch': '0fe8fcd2c7b158af26d87a73082c2069b9a5883e4f979e81f3b6234415a6043d',
}


PLATFORM_PROTECTED: dict[str, str] = {
    '/app/bin/catalog-query': '3ad8e7bb488588723aec2e8db96d16dca68ed624c3d9068721080eb37e311eb6',
    '/app/bin/harbor-relay': '3659d09b252a30e6965879adbb8ca9263e47699bd978964596153a8d8f18a7d8',
    '/opt/harbor-platform-source/include/config.hpp': '1e6fbc82c9076bbdc98cb36de9a939b4eb421cb92aa42950b4f218a6dbeb6be8',
    '/opt/harbor-platform-source/include/http.hpp': 'de0ffe20113f3772f16101a522ad2ae8aa5db90b2597fa513d7d5a68dd62bc51',
    '/opt/harbor-platform-source/include/route.hpp': '08f78348b76aec62275012ec4f7e42ae623b306de9369cd81db7bccf3bb5860b',
    '/opt/harbor-platform-source/include/util.hpp': 'f1e6d2310b5c6effe8c743e5a5fbec5a6e4ad593b6d8addb73804cc60eb60df0',
    '/opt/harbor-platform-source/src/config.cpp': '58b147730da60d9d0ba122293d0629d6264ea24208497312a9b0e7d1bb87b7f0',
    '/opt/harbor-platform-source/src/http.cpp': '3b8bb441fe82dae6c0909249291848db8562f128f5e6e1f810a1d563005573ff',
    '/opt/harbor-platform-source/src/relay_main.cpp': '343190efadfd21414ad5137a9bdf949fe6e4abec553dc53d53a260093cfed427',
    '/opt/harbor-platform-source/src/route.cpp': '882eaed9095eddc44055bb62fe59943cfe0c65532c640c77e349bf2d9c731f3b',
    '/opt/harbor-platform-source/src/util.cpp': 'c0e8a8646f30376058a73ba52fa961cc71deb0da2c9f1c0f068d0c6c5933337f',
    '/opt/harbor-platform-source/tools/catalog_query.cpp': '2ef4ef31ece3a5d2b6a0a6fb86e5a985d79cbaf3bba4293ba7efe49848f2f6b9',
}
EXPECTED_RELAY = {
    "site_key": "st-042",
    "socket_path": "/app/run/harbor-relay/service-window.sock",
    "socket_mode": "0660",
    "socket_owner": "relayops",
    "socket_group": "relay",
    "listen_backlog": "128",
    "route_map": "/app/etc/harbor-relay/routes.map",
    "limits_file": "/app/etc/harbor-relay/limits.conf",
    "audit_db": "/app/var/commissioning-ledger.db",
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
EXPECTED_ACKNOWLEDGMENTS = [
    {
        "work_group": "network",
        "operator_id": "bob.net",
        "role_code": "NETWORK",
        "weight": 2,
        "state": "restore",
        "event_id": "ev-b3",
    },
    {
        "work_group": "operations",
        "operator_id": "alice.ops",
        "role_code": "OPS",
        "weight": 2,
        "state": "acknowledge",
        "event_id": "ev-a1",
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
    if database.name == "maintenance-window.db":
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
        "socket-allocation-review.md",
        "route-allocation-register.md",
        "capacity-planning-notes.md",
        "maintenance-window-governance.md",
        "commissioning-ledger-minutes.md",
    ]


def test_catalog_interfaces_and_platform_binaries_remain_valid() -> None:
    """Verify both sealed catalogs and existing relay binaries remain usable with immutable platform source."""
    assert logical_database_digest(Path("/opt/harbor/service-catalog.db")) == "98d7c4d84f4df5cf2c154e0853d4b9a1db9662c281d4dead2d1334bbbb83280e"
    assert logical_database_digest(Path("/opt/harbor/maintenance-window.db")) == "0e6c88f6dc0ae3b7bc3ada64872acf493923761fb1616903c9412dd2e5378590"
    operations = query_catalog(Path("/opt/harbor/service-catalog.db"), APP / "share/service-catalog.batch")
    changes = query_catalog(Path("/opt/harbor/maintenance-window.db"), APP / "share/maintenance-window.batch")
    assert operations.startswith(b"@result catalog_meta\n") and operations.rstrip().endswith(b"@end")
    assert changes.startswith(b"@result schedule_meta\n") and changes.rstrip().endswith(b"@end")
    check = subprocess.run(
        [str(APP / "bin/harbor-relay"), "--check-config", str(CONFIG_DIR / "relay.conf")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert check.returncode == 0, check.stderr
    source_root = Path("/opt/harbor-platform-source")
    assert (source_root / "src/relay_main.cpp").is_file()
    assert (source_root / "tools/catalog_query.cpp").is_file()
    for path_text, expected in PLATFORM_PROTECTED.items():
        path = Path(path_text)
        assert path.is_file(), path_text
        assert sha256(path) == expected, path_text
    assert all(not (path.stat().st_mode & 0o222) for path in source_root.rglob("*") if path.is_file())


def test_commissioned_configuration_matches_allocated_socket_routes_and_limits() -> None:
    """Verify the installed text configuration contains the allocated socket, routes, and limits."""
    relay_path = CONFIG_DIR / "relay.conf"
    limits_path = CONFIG_DIR / "limits.conf"
    routes_path = CONFIG_DIR / "routes.map"
    assert read_key_values(relay_path) == EXPECTED_RELAY
    assert read_key_values(limits_path) == EXPECTED_LIMITS
    route_lines = routes_path.read_text(encoding="utf-8").splitlines()
    assert route_lines[0] == "method\texternal_path\tupstream\tauth_mode\ttimeout_ms\tsource_route_id"
    assert [tuple(line.split("\t")) for line in route_lines[1:]] == EXPECTED_ROUTES
    assert all(path.read_bytes().endswith(b"\n") for path in [relay_path, limits_path, routes_path])
    unit_lines = UNIT.read_text(encoding="utf-8").splitlines()
    assert "User=relayops" in unit_lines
    assert "Group=relay" in unit_lines
    assert "ExecStart=/app/bin/harbor-relay --config /app/etc/harbor-relay/relay.conf" in unit_lines
    assert "LimitNOFILE=640" in unit_lines
    assert "UMask=0007" in unit_lines
    trace = (APP / "records/socket-allocation-events.txt").read_text(encoding="utf-8")
    assert "data-plane.sock\"" in trace and "EACCES" in trace
    after = (APP / "records/socket-occupancy-snapshot.txt").read_text(encoding="utf-8").split("# snapshot=after", 1)[1]
    assert EXPECTED_RELAY["socket_path"] not in after


def test_window_plan_reconciles_order_acknowledgments_slot_and_identity() -> None:
    """Verify the maintenance order, effective acknowledgments, service slot, and window identity."""
    raw = WINDOW_PLAN.read_text(encoding="utf-8")
    plan = json.loads(raw)
    assert raw == json.dumps(plan, separators=(",", ":")) + "\n"
    assert list(plan) == [
        "order_id",
        "schedule_generation",
        "slot_id",
        "service_lane",
        "ack_weight_required",
        "ack_weight_observed",
        "acknowledgments",
        "readiness_digest",
        "launch_token",
    ]
    assert plan["order_id"] == "mw-2026-071"
    assert plan["schedule_generation"] == 11
    assert plan["slot_id"] == "slot-071-window-b4"
    assert plan["service_lane"] == "BLUE"
    assert (plan["ack_weight_required"], plan["ack_weight_observed"]) == (4, 4)
    assert plan["acknowledgments"] == EXPECTED_ACKNOWLEDGMENTS
    member_lines = [
        "|".join(
            [
                item["work_group"],
                item["operator_id"],
                item["role_code"],
                str(item["weight"]),
                item["state"],
                item["event_id"],
            ]
        )
        for item in EXPECTED_ACKNOWLEDGMENTS
    ]
    assert plan["readiness_digest"] == digest_lines(member_lines)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    token_seed = "|".join(
        [plan["order_id"], plan["slot_id"], plan["readiness_digest"], manifest["run_id"]]
    )
    assert plan["launch_token"] == hashlib.sha256(token_seed.encode()).hexdigest()[:24]
    assert manifest["window_plan"] == plan


def test_service_generation_permissions_and_clean_state_are_correct() -> None:
    """Verify all documented generation files have required modes and no prohibited residue remains."""
    expected_modes = {
        CONFIG_DIR / "relay.conf": 0o640,
        CONFIG_DIR / "limits.conf": 0o640,
        CONFIG_DIR / "routes.map": 0o640,
        WINDOW_PLAN: 0o640,
        AUDIT: 0o600,
        MANIFEST: 0o640,
        LOCK: 0o600,
        UNIT: 0o644,
    }
    for path, mode in expected_modes.items():
        assert path.is_file(), path
        assert stat.S_IMODE(path.stat().st_mode) == mode
    assert LOCK.stat().st_size == 0
    relay_gid = grp.getgrnam("relay").gr_gid
    relay_uid = pwd.getpwnam("relayops").pw_uid
    for path in [CONFIG_DIR / "relay.conf", CONFIG_DIR / "limits.conf", CONFIG_DIR / "routes.map"]:
        assert (path.stat().st_uid, path.stat().st_gid) == (0, relay_gid)
    for path in [WINDOW_PLAN, AUDIT, MANIFEST, LOCK]:
        assert (path.stat().st_uid, path.stat().st_gid) == (relay_uid, relay_gid)
    assert (UNIT.stat().st_uid, UNIT.stat().st_gid) == (0, 0)
    run_dir = APP / "run/harbor-relay"
    assert stat.S_IMODE(run_dir.stat().st_mode) == 0o750
    assert (run_dir.stat().st_uid, run_dir.stat().st_gid) == (relay_uid, relay_gid)
    residue = []
    for directory in [CONFIG_DIR, APP / "var"]:
        residue.extend(
            path
            for path in directory.iterdir()
            if any(token in path.name for token in (".tmp", ".bak", "-journal", "-wal", "-shm"))
        )
    assert residue == []


def test_commissioning_manifest_has_deterministic_identity_and_exact_provenance() -> None:
    """Verify compact manifest identity, ordering, two-catalog provenance, and publication metadata."""
    raw = MANIFEST.read_text(encoding="utf-8")
    manifest = json.loads(raw)
    assert raw == json.dumps(manifest, separators=(",", ":")) + "\n"
    assert list(manifest) == [
        "run_id",
        "site_key",
        "handbook_revision",
        "catalog_generation",
        "schedule_generation",
        "configuration",
        "routes",
        "assertions",
        "window_plan",
        "inputs",
        "publication",
    ]
    assert manifest["site_key"] == "st-042"
    assert manifest["handbook_revision"] == "HRH-2026.07-R11"
    assert (manifest["catalog_generation"], manifest["schedule_generation"]) == (29, 11)
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
    expected_inputs = [
        ("catalog-batch-result", "/app/share/service-catalog.batch"),
        ("maintenance-window-batch-result", "/app/share/maintenance-window.batch"),
        ("request-manifest", "/app/fixtures/requests/replay-set.manifest"),
        ("request:arrival", "/app/fixtures/requests/arrival-replay.http"),
        ("request:manifest", "/app/fixtures/requests/manifest-replay.http"),
        ("request:status", "/app/fixtures/requests/status-replay.http"),
        ("socket-inventory", "/app/records/socket-occupancy-snapshot.txt"),
        ("socket-open-trace", "/app/records/socket-allocation-events.txt"),
        ("window-meta", "/app/records/window.meta"),
    ]
    assert [(item["kind"], item["path"]) for item in manifest["inputs"]] == expected_inputs

    request_paths = [APP / "fixtures/requests/replay-set.manifest"]
    for line in request_paths[0].read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            request_paths.append(Path(line.split("\t", 1)[1]))
    request_set = digest_lines([sha256(path) for path in request_paths])
    record_set = digest_lines(
        [
            sha256(APP / "records/window.meta"),
            sha256(APP / "records/socket-allocation-events.txt"),
            sha256(APP / "records/socket-occupancy-snapshot.txt"),
        ]
    )
    operations_snapshot = query_catalog(
        Path("/opt/harbor/service-catalog.db"), APP / "share/service-catalog.batch"
    )
    schedule_snapshot = query_catalog(
        Path("/opt/harbor/maintenance-window.db"), APP / "share/maintenance-window.batch"
    )
    operations_sha = hashlib.sha256(operations_snapshot).hexdigest()
    schedule_sha = hashlib.sha256(schedule_snapshot).hexdigest()
    seed = "|".join(
        [
            "st-042",
            "HRH-2026.07-R11",
            "29",
            "11",
            request_set,
            record_set,
            operations_sha,
            schedule_sha,
            manifest["window_plan"]["readiness_digest"],
            sha256(CONFIG_DIR / "relay.conf"),
            sha256(CONFIG_DIR / "limits.conf"),
            sha256(CONFIG_DIR / "routes.map"),
            sha256(UNIT),
        ]
    )
    assert manifest["run_id"] == hashlib.sha256(seed.encode()).hexdigest()[:24]

    inputs = {(item["kind"], item["path"]): item for item in manifest["inputs"]}
    operations_item = inputs[("catalog-batch-result", "/app/share/service-catalog.batch")]
    schedule_item = inputs[("maintenance-window-batch-result", "/app/share/maintenance-window.batch")]
    assert (operations_item["sha256"], operations_item["bytes"]) == (
        operations_sha,
        len(operations_snapshot),
    )
    assert (schedule_item["sha256"], schedule_item["bytes"]) == (schedule_sha, len(schedule_snapshot))
    for (kind, path_text), item in inputs.items():
        if kind.endswith("batch-result"):
            continue
        path = Path(path_text)
        assert (item["sha256"], item["bytes"]) == (sha256(path), path.stat().st_size)

    expected_publication = [
        (CONFIG_DIR / "relay.conf", "0640"),
        (CONFIG_DIR / "limits.conf", "0640"),
        (CONFIG_DIR / "routes.map", "0640"),
        (WINDOW_PLAN, "0640"),
        (UNIT, "0644"),
        (AUDIT, "0600"),
        (MANIFEST, "0640"),
    ]
    assert [item["path"] for item in manifest["publication"]] == [
        str(path) for path, _ in expected_publication
    ]
    for item, (path, mode) in zip(manifest["publication"], expected_publication, strict=True):
        assert list(item) == ["path", "sha256", "bytes", "mode"]
        assert item["mode"] == mode
        if path in {AUDIT, MANIFEST}:
            assert (item["sha256"], item["bytes"]) == (ZERO, 0)
        else:
            assert (item["sha256"], item["bytes"]) == (sha256(path), path.stat().st_size)


def test_commissioning_ledger_schema_constraints_and_reconciliation_are_complete() -> None:
    """Verify the nine-table ledger, twenty decisions, two acknowledgments, and seven publication rows."""
    with sqlite3.connect(AUDIT) as database:
        assert database.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        tables = [
            row[0]
            for row in database.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY rowid")
        ]
        assert tables == [
            "commissioning_run",
            "input_artifact",
            "configuration",
            "route",
            "decision",
            "assertion",
            "window_plan",
            "acknowledgment",
            "publication_file",
        ]
        run = database.execute(
            "SELECT run_id,site_key,handbook_revision,catalog_generation,schedule_generation,status "
            "FROM commissioning_run"
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
        window_plan = database.execute(
            "SELECT order_id,schedule_generation,slot_id,service_lane,ack_weight_required,"
            "ack_weight_observed,readiness_digest,launch_token FROM window_plan"
        ).fetchone()
        plan = json.loads(WINDOW_PLAN.read_text(encoding="utf-8"))
        assert window_plan == (
            plan["order_id"],
            11,
            plan["slot_id"],
            plan["service_lane"],
            4,
            4,
            plan["readiness_digest"],
            plan["launch_token"],
        )
        acknowledgment_rows = database.execute(
            "SELECT work_group,operator_id,role_code,weight,state,event_id "
            "FROM acknowledgment ORDER BY work_group,operator_id"
        ).fetchall()
        assert acknowledgment_rows == [
            tuple(item[key] for key in ("work_group", "operator_id", "role_code", "weight", "state", "event_id"))
            for item in EXPECTED_ACKNOWLEDGMENTS
        ]
        publication = {
            row[0]: row[1:]
            for row in database.execute("SELECT path,sha256,bytes,mode_text FROM publication_file")
        }
        assert publication[str(WINDOW_PLAN)] == (sha256(WINDOW_PLAN), WINDOW_PLAN.stat().st_size, "0640")
        assert publication[str(UNIT)] == (sha256(UNIT), UNIT.stat().st_size, "0644")
        assert publication[str(AUDIT)] == (ZERO, 0, "0600")
        assert publication[str(MANIFEST)] == (ZERO, 0, "0640")
        assert database.execute(
            "SELECT evidence FROM decision WHERE sequence=3 AND domain='socket'"
        ).fetchone() == ("last=EACCES",)
        assert database.execute(
            "SELECT subject,outcome FROM decision WHERE sequence=18 AND domain='maintenance-window'"
        ).fetchone() == ("carol.sre", "rejected")
    with sqlite3.connect(AUDIT) as database:
        statements = Path("/tests/commissioning_assertions.sql").read_text(encoding="utf-8").split(";")
        for statement in statements:
            if statement.strip():
                assert database.execute(statement).fetchone() == (1,)


def test_commissioned_relay_serves_required_missing_and_oversized_requests() -> None:
    """Verify the existing relay binds the socket and serves all required HTTP outcomes."""
    socket_path = Path(EXPECTED_RELAY["socket_path"])
    socket_path.unlink(missing_ok=True)
    process = subprocess.Popen(
        ["runuser", "-u", "relayops", "--", str(APP / "bin/harbor-relay"), "--config", str(CONFIG_DIR / "relay.conf")],
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
        relay_gid = grp.getgrnam("relay").gr_gid
        relay_uid = pwd.getpwnam("relayops").pw_uid
        assert (socket_path.stat().st_uid, socket_path.stat().st_gid) == (relay_uid, relay_gid)
        assert stat.S_IMODE(socket_path.stat().st_mode) == 0o660
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        socket_path.unlink(missing_ok=True)
