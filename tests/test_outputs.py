"""Verifier for cabrelay host duty-transfer control plane."""

from __future__ import annotations

import csv
import json
import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path("/app/var")
OUT = Path("/app/output")
CFG = Path("/app/environment/configs/transfer.toml")
CFG_ALT = Path("/app/environment/configs/transfer_alt.toml")
CFG_BAD = Path("/app/environment/configs/transfer_invalid.toml")


@pytest.fixture(scope="session", autouse=True)
def _rebuild() -> None:
    subprocess.run(["/app/environment/scripts/build.sh"], check=True)


def _reset_root() -> None:
    if ROOT.exists():
        shutil.rmtree(ROOT)
    if OUT.exists():
        shutil.rmtree(OUT)
    ROOT.mkdir(parents=True)
    OUT.mkdir(parents=True)
    (ROOT / "deskstate").mkdir(parents=True)
    os.chown(ROOT / "deskstate", 1100, 2100)
    os.chmod(ROOT / "deskstate", 0o755)


def _run(args: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["go", "run", "./cmd/cabrelay", *args],
        cwd="/app/environment",
        text=True,
        capture_output=True,
        check=check,
        env={**os.environ, "PATH": "/usr/local/go/bin:" + os.environ.get("PATH", "")},
    )


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _dropin_text(unit: str = "desk.service") -> str:
    return (ROOT / "units" / f"{unit}.d" / "override.conf").read_text()


def _xattr_seal(path: Path) -> str:
    return os.getxattr(path, "user.cabrelay.seal").decode()


def _oct_mode(path: Path) -> str:
    full = path.stat().st_mode
    mode = stat.S_IMODE(full)
    if full & stat.S_ISGID:
        mode |= 0o2000
    return f"{mode:05o}" if mode > 0o777 else f"{mode:04o}"


def _mesh_digest(seal: str, supp_csv: str) -> str:
    return f"{seal}|{supp_csv}"


def _assert_export_bundle(st: dict, seal: str, supp_csv: str, uid: int, gid: int, user: str) -> None:
    cur = _read_json(ROOT / "ledger" / "cursor.json")
    mesh = _read_json(ROOT / "mesh" / "slice.json")
    recon = _read_json(OUT / "mesh_reconcile.json")
    desk = ROOT / "deskstate"
    sock = ROOT / "sockets" / "desk.sock"
    drop = _dropin_text()

    assert st["epoch"] == cur["epoch"] == mesh["epoch"]
    assert st["phase"] == cur["phase"]
    assert cur["phase"] == mesh["phase"] or mesh["phase"] == "live"
    assert mesh["phase"] == "live"
    assert st["unit_user"] == user
    assert f"User={user}" in drop
    assert f"Group={gid}" in drop
    assert f"SupplementaryGroups={supp_csv}" in drop
    assert desk.stat().st_uid == uid
    assert desk.stat().st_gid == gid
    assert _oct_mode(desk) == "02750"
    assert _xattr_seal(desk) == seal == st["seal"] == cur["seal"]
    assert sock.is_socket()
    assert sock.stat().st_gid == gid
    assert _oct_mode(sock) == "0660"
    assert st["socket_gid"] == gid
    assert st["custody_uid"] == uid
    assert st["custody_gid"] == gid
    assert st["mesh_digest"] == _mesh_digest(seal, supp_csv) == mesh["digest"]
    assert mesh["holder_uid"] == uid
    assert mesh["holder_gid"] == gid
    assert mesh["supp_csv"] == supp_csv
    assert recon["seal"] == seal
    assert recon["mesh_digest"] == st["mesh_digest"]
    assert recon["unit_user"] == user
    assert recon["custody_uid"] == uid
    assert recon["socket_gid"] == gid
    assert recon["epoch"] == st["epoch"]
    assert recon["prior_seal"] == st["prior_seal"] == cur["prior_seal"]

    with (OUT / "custody.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    assert rows[0]["uid"] == str(uid)
    assert rows[0]["gid"] == str(gid)
    assert rows[0]["mode"] == "02750"
    assert rows[0]["seal"] == seal

    cli = _run(["status", "--root", str(ROOT)], check=True)
    live = json.loads(cli.stdout)
    for key in (
        "epoch",
        "phase",
        "unit_user",
        "unit_gid",
        "custody_uid",
        "custody_gid",
        "custody_mode",
        "seal",
        "socket_mode",
        "socket_gid",
        "mesh_digest",
        "prior_seal",
    ):
        assert live[key] == st[key]


def test_apply_cross_artifact_coherence():
    """Successful apply keeps drop-in, custody, ledger, mesh, socket, and exports aligned."""
    _reset_root()
    proc = _run(["apply", "--config", str(CFG), "--root", str(ROOT)])
    assert proc.returncode == 0, proc.stderr
    st = _read_json(OUT / "status.json")
    assert st["finish_reason"] == "applied"
    seal = "1:1101:2101"
    _assert_export_bundle(st, seal, "2102,2103", 1101, 2101, "ctrl_b")
    assert st["prior_seal"] == ""


def test_mutation_alt_principals_and_group_sort():
    """Mutated principal ids and unsorted supplementary groups still sort and bind."""
    _reset_root()
    proc = _run(["apply", "--config", str(CFG_ALT), "--root", str(ROOT)])
    assert proc.returncode == 0, proc.stderr
    st = _read_json(OUT / "status.json")
    _assert_export_bundle(st, "1:1205:2205", "2208,2209,2210", 1205, 2205, "ops_day")


def test_held_out_principal_matrix():
    """A held-out TOML not shipped as a named fixture still satisfies the same invariants."""
    _reset_root()
    body = """
[principals]
outgoing_user = "night_ops"
outgoing_uid = 1300
outgoing_gid = 2300
incoming_user = "day_ops"
incoming_uid = 1307
incoming_gid = 2307
supplementary_groups = [2311, 2309, 2310]

[runtime]
unit_name = "desk.service"
"""
    with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as fh:
        fh.write(body)
        cfg = fh.name
    try:
        proc = _run(["apply", "--config", cfg, "--root", str(ROOT)])
        assert proc.returncode == 0, proc.stderr
        st = _read_json(OUT / "status.json")
        _assert_export_bundle(st, "1:1307:2307", "2309,2310,2311", 1307, 2307, "day_ops")
    finally:
        os.unlink(cfg)


def test_invalid_config_is_negative_path():
    """Invalid incoming principal leaves host state untouched."""
    _reset_root()
    before_uid = (ROOT / "deskstate").stat().st_uid
    before_epoch = 0
    proc = _run(["apply", "--config", str(CFG_BAD), "--root", str(ROOT)])
    assert proc.returncode != 0
    assert not (ROOT / "units" / "desk.service.d" / "override.conf").exists()
    assert not (ROOT / "sockets" / "desk.sock").exists()
    assert (ROOT / "deskstate").stat().st_uid == before_uid
    if (ROOT / "mesh" / "slice.json").exists():
        assert _read_json(ROOT / "mesh" / "slice.json").get("phase") != "live"
    st = _read_json(OUT / "status.json")
    assert st["finish_reason"] not in ("applied", "resumed")
    assert st["epoch"] == before_epoch


def test_crash_inject_then_resume_single_epoch():
    """Crash marker stops before fence; resume commits exactly one epoch."""
    _reset_root()
    (ROOT / "ledger").mkdir(parents=True, exist_ok=True)
    (ROOT / "ledger" / "crash.inject").write_text("1\n")
    before = 0
    proc = _run(["apply", "--config", str(CFG), "--root", str(ROOT)])
    assert proc.returncode != 0
    cur = _read_json(ROOT / "ledger" / "cursor.json")
    mesh = _read_json(ROOT / "mesh" / "slice.json")
    assert cur["phase"] != "committed"
    assert cur["epoch"] == before
    assert mesh["phase"] != "live"
    assert mesh["epoch"] == before
    assert (ROOT / "units" / "desk.service.d" / "override.conf").exists()
    assert not (ROOT / "sockets" / "desk.sock").exists()
    journal = (ROOT / "ledger" / "journal.ndjson").read_text().strip().splitlines()
    assert any(json.loads(line)["result"] != "ok" for line in journal)

    blocked = _run(["apply", "--config", str(CFG), "--root", str(ROOT)])
    assert blocked.returncode != 0
    assert _read_json(ROOT / "ledger" / "cursor.json")["epoch"] == before

    proc2 = _run(["resume", "--config", str(CFG), "--root", str(ROOT)])
    assert proc2.returncode == 0, proc2.stderr
    st = _read_json(OUT / "status.json")
    assert st["finish_reason"] == "resumed"
    _assert_export_bundle(st, "1:1101:2101", "2102,2103", 1101, 2101, "ctrl_b")


def test_second_apply_advances_epoch_and_prior_seal():
    """Two clean applies advance the ledger by two and retain prior seal/digest."""
    _reset_root()
    assert _run(["apply", "--config", str(CFG), "--root", str(ROOT)]).returncode == 0
    first_seal = _xattr_seal(ROOT / "deskstate")
    first_digest = _read_json(ROOT / "mesh" / "slice.json")["digest"]
    first_epoch = _read_json(ROOT / "ledger" / "cursor.json")["epoch"]
    assert _run(["apply", "--config", str(CFG), "--root", str(ROOT)]).returncode == 0
    st = _read_json(OUT / "status.json")
    mesh = _read_json(ROOT / "mesh" / "slice.json")
    assert st["epoch"] == first_epoch + 1
    assert st["seal"] != first_seal
    assert st["prior_seal"] == first_seal
    assert mesh["prior_digest"] == first_digest
    assert mesh["digest"] == _mesh_digest(st["seal"], "2102,2103")
    _assert_export_bundle(st, st["seal"], "2102,2103", 1101, 2101, "ctrl_b")


def test_socket_not_open_against_stale_pending_seal():
    """Incomplete crash work must not open the desk socket before custody completes."""
    _reset_root()
    (ROOT / "ledger").mkdir(parents=True, exist_ok=True)
    (ROOT / "ledger" / "crash.inject").write_text("1\n")
    _run(["apply", "--config", str(CFG), "--root", str(ROOT)])
    assert not (ROOT / "sockets" / "desk.sock").exists()
    mesh = _read_json(ROOT / "mesh" / "slice.json")
    assert mesh["phase"] != "live"
    assert mesh.get("digest", "") == ""
    assert _run(["resume", "--config", str(CFG), "--root", str(ROOT)]).returncode == 0
    seal = _xattr_seal(ROOT / "deskstate")
    st = _read_json(OUT / "status.json")
    assert seal == st["seal"]
    assert st["socket_gid"] == st["custody_gid"]
    assert st["mesh_digest"].startswith(seal + "|")


def test_status_rereads_live_host_not_stale_file():
    """Status must reflect live drop-in/mesh mutations, not a leftover status.json."""
    _reset_root()
    assert _run(["apply", "--config", str(CFG), "--root", str(ROOT)]).returncode == 0
    stale = _read_json(OUT / "status.json")
    drop = ROOT / "units" / "desk.service.d" / "override.conf"
    drop.write_text(drop.read_text().replace("User=ctrl_b", "User=mutated_ops"))
    mesh_path = ROOT / "mesh" / "slice.json"
    mesh = _read_json(mesh_path)
    mesh["digest"] = "mutated-live-digest"
    mesh_path.write_text(json.dumps(mesh, indent=2) + "\n")

    cli = _run(["status", "--root", str(ROOT)], check=True)
    live = json.loads(cli.stdout)
    assert live["unit_user"] == "mutated_ops"
    assert live["mesh_digest"] == "mutated-live-digest"
    assert stale["unit_user"] != "mutated_ops"
    assert stale["mesh_digest"] != "mutated-live-digest"
    assert _read_json(OUT / "status.json")["unit_user"] == stale["unit_user"]
