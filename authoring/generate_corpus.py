#!/usr/bin/env python3
"""Deterministic access/signing journal corpus for go-cert-path-revocation-hard.

Regenerates the shipped visible journal under environment/data/access/access.journal
and the held-out grading shard under tests/data/access/held_out.journal.

Re-running with the same PKI on disk reproduces the shipped bytes exactly.
"""
from __future__ import annotations

import hashlib
import sqlite3
import struct
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import NameOID

ROOT = Path(__file__).resolve().parents[1]
ENV_DATA = ROOT / "environment" / "data"
ACCESS = ENV_DATA / "access"
VISIBLE = ACCESS / "access.journal"
HELD_OUT = ROOT / "tests" / "data" / "access" / "held_out.journal"
AUDIT_DB = ACCESS / "access_audit.db"

RNG_SEED = 0x00007741
VISIBLE_SIGN_TARGET = 3524
HELD_SIGN_TARGET = 3518

# Original ACCESS fixtures (join tests depend on these exact tuples).
CORE_ACCESS: list[dict[str, Any]] = [
    {
        "record_id": "fs-001",
        "cert_fp": "fc662200da24da2480aa1b7a6996b3d7ee5b957fe4044f3f595387ea3176f3b2",
        "service_id": "edge-gateway",
        "access_ts": "2026-01-15T10:30:45Z",
        "bytes_read": 4097,
        "kind": "joined",
    },
    {
        "record_id": "fs-002",
        "cert_fp": "208fe4a3f8562ced1be9ff54e0b1a3cbc8ea6a4d6d86958a0ce9af07822cba65",
        "service_id": "mesh-proxy",
        "access_ts": "2026-01-15T11:00:12Z",
        "bytes_read": 4098,
        "kind": "joined",
    },
    {
        "record_id": "fs-003",
        "cert_fp": "b38f68c6e4116df7b5779e4b1f78231829ca57f3be60ec49a720e84f1f03d8e8",
        "service_id": "mesh-proxy",
        "access_ts": "2026-01-15T11:00:55Z",
        "bytes_read": 4099,
        "kind": "joined",
    },
    {
        "record_id": "fs-004",
        "cert_fp": "23c1ab4eb4fa17782e6bef1e7c87f7c1e0dbe5670c60ad822681a49ba9d60bd5",
        "service_id": "legacy-ingest",
        "access_ts": "2026-01-15T12:15:00Z",
        "bytes_read": 4100,
        "kind": "fs_only",
    },
    {
        "record_id": "fs-006",
        "cert_fp": "282b7727e49e973baf41a55c66563f598eb8f8b8c5d9f7fd2df183d692b72dff",
        "service_id": "legacy-ingest",
        "access_ts": "2026-01-15T12:14:30Z",
        "bytes_read": 4102,
        "kind": "joined",
    },
]

CUSTODIANS = {
    "cust-alpha": ("2025-01-01T00:00:00Z", "2027-01-01T00:00:00Z"),
    "cust-bravo": ("2025-01-01T00:00:00Z", "2027-01-01T00:00:00Z"),
    "cust-charlie": ("2025-01-01T00:00:00Z", "2027-01-01T00:00:00Z"),
    "cust-echo": ("2026-02-01T00:00:00Z", "2027-01-01T00:00:00Z"),
    "cust-foxtrot": ("2025-01-01T00:00:00Z", "2025-12-01T00:00:00Z"),
}

IN_WINDOW_SIGNERS = ("cust-alpha", "cust-bravo", "cust-charlie")

# Spread indices chosen after bulk length is known (see insert_spread).
VISIBLE_OOW_INSERT_AT = (712, 1488, 2264, 3016)


class _LCG:
    def __init__(self, seed: int) -> None:
        self._state = seed & 0xFFFFFFFFFFFFFFFF

    def randbelow(self, n: int) -> int:
        self._state = (6364136223846793005 * self._state + 1) & 0xFFFFFFFFFFFFFFFF
        return self._state % n

    def choice(self, items: list[Any]) -> Any:
        return items[self.randbelow(len(items))]


def fp_of(cert: x509.Certificate) -> str:
    return hashlib.sha256(cert.public_bytes(Encoding.DER)).hexdigest()


def load_fps() -> dict[str, str]:
    out: dict[str, str] = {}
    for folder in (ENV_DATA / "leaves", ENV_DATA / "authorities"):
        for pem in sorted(folder.glob("*.pem")):
            cert = x509.load_pem_x509_certificate(pem.read_bytes())
            cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
            out[pem.stem] = fp_of(cert)
            out[cn] = fp_of(cert)
    return out


def join_key(cert_fp: str, service_id: str, access_ts: str) -> str:
    minute = access_ts[:16]
    raw = f"{cert_fp}:{service_id}:{minute}".encode()
    return hashlib.sha256(raw).hexdigest()


def access_line(rec: dict[str, Any]) -> str:
    return (
        f"ACCESS cert_fp={rec['cert_fp']} service={rec['service_id']} "
        f"ts={rec['access_ts']} record={rec['record_id']} bytes={rec['bytes_read']}"
    )


def sign_line(rec: dict[str, str]) -> str:
    return (
        f"SIGN cert_fp={rec['cert_fp']} signer={rec['signer_id']} "
        f"ts={rec['event_ts']} record={rec['record_id']}"
    )


def ts_from_slot(slot: int) -> str:
    day = 1 + (slot % 28)
    hour = slot % 24
    minute = (slot // 24) % 60
    second = (slot // (24 * 60)) % 60
    return f"2026-01-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}Z"


def write_access_db() -> None:
    if AUDIT_DB.exists():
        AUDIT_DB.unlink()
    conn = sqlite3.connect(AUDIT_DB)
    conn.execute("PRAGMA page_size=4096")
    conn.execute(
        """CREATE TABLE access_records (
            record_id TEXT PRIMARY KEY,
            cert_fp TEXT NOT NULL,
            service_id TEXT NOT NULL,
            access_ts TEXT NOT NULL,
            join_key TEXT NOT NULL,
            audit_seq INTEGER NOT NULL
        )"""
    )
    audit_seq = 100
    for rec in CORE_ACCESS:
        if rec["kind"] in ("joined", "db_only"):
            ts = rec["access_ts"]
            conn.execute(
                "INSERT INTO access_records VALUES (?,?,?,?,?,?)",
                (
                    rec["record_id"].replace("fs", "db"),
                    rec["cert_fp"],
                    rec["service_id"],
                    ts,
                    join_key(rec["cert_fp"], rec["service_id"], ts),
                    audit_seq,
                ),
            )
            audit_seq += 1
    expired_fp = "da7edb3b5fa7e358f4b9a2c1d0e3f6a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4"
    for pem in (ENV_DATA / "leaves").glob("leaf-expired.pem"):
        expired_fp = fp_of(x509.load_pem_x509_certificate(pem.read_bytes()))
    conn.execute(
        "INSERT INTO access_records VALUES (?,?,?,?,?,?)",
        (
            "db-005",
            expired_fp,
            "batch-runner",
            "2026-01-15T13:00:22Z",
            join_key(expired_fp, "batch-runner", "2026-01-15T13:00:22Z"),
            audit_seq,
        ),
    )
    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    raw = AUDIT_DB.read_bytes()
    if len(raw) >= 100:
        patched = bytearray(raw)
        struct.pack_into(">I", patched, 60, 7741)
        AUDIT_DB.write_bytes(bytes(patched))


def bulk_sign_events(
    rng: _LCG,
    fps: list[str],
    count: int,
    *,
    start_id: int,
    signer_pool: tuple[str, ...],
) -> list[str]:
    lines: list[str] = []
    for i in range(count):
        cert_fp = rng.choice(fps)
        signer = rng.choice(list(signer_pool))
        slot = start_id + i
        event_ts = ts_from_slot(slot)
        rec = {
            "cert_fp": cert_fp,
            "signer_id": signer,
            "event_ts": event_ts,
            "record_id": f"sg-{start_id + i:05d}",
        }
        lines.append(sign_line(rec))
    return lines


def insert_spread(lines: list[str], inserts: list[tuple[int, str]]) -> None:
    for idx, line in sorted(inserts, key=lambda t: t[0]):
        pos = min(idx, len(lines))
        lines.insert(pos, line)


# A compromised leaf becomes an implicit containment subject, so every sound path it
# owns has to be cut by distrusting some authority on that path. Leaves issued directly
# by a root can only be cut at the root itself, and the preserve subject leaf-xc-keep
# reaches its only anchor through root-a, so containing such a leaf leaves the incident
# with no satisfiable answer at all. Restrict traps to leaves that can be cut at an
# intermediate; picking leaf-accept-direct here once made the whole run panic.
#
# Two leaves clear that bar and still cause damage: leaf-crosspath and leaf-revoked-byfp
# are cheapest to cut at root-b, and distrusting a root cascades over the expired and
# not-yet-valid leaves, collapsing their rejection reasons into revoked and destroying
# the reason coverage the suite depends on. Both are excluded here for that reason.
SAFE_OOW_TARGETS = frozenset(
    {
        "leaf-accept-a1",
        "leaf-accept-deep",
        "leaf-mesh-cascade",
        "leaf-multi",
        "leaf-revoked-byname",
        "leaf-revoked-byname-deep",
        "leaf-ring-cycle",
        "leaf-xc-one",
        "leaf-xc-two",
    }
)


def visible_oow_traps(fps_map: dict[str, str]) -> list[dict[str, str]]:
    """Out-of-window events in the visible corpus; join-only detectable."""
    # All four visible traps are no-new-cut leaves: making them compromised moves the
    # digest and the tainted_members list but does not change the minimum containment
    # set. The two later traps sit past the point where a reader who stops early would
    # have quit, so partial coverage still produces a self-consistent, wrong answer.
    return [
        {
            "cert_fp": fps_map["leaf-mesh-cascade"],
            "signer_id": "cust-foxtrot",
            "event_ts": "2026-01-15T12:00:00Z",
            "record_id": "sg-oow-v-001",
        },
        {
            "cert_fp": fps_map["leaf-ring-cycle"],
            "signer_id": "cust-echo",
            "event_ts": "2026-01-18T14:22:00Z",
            "record_id": "sg-oow-v-002",
        },
        {
            "cert_fp": fps_map["leaf-revoked-byname"],
            "signer_id": "cust-foxtrot",
            "event_ts": "2026-01-22T09:11:00Z",
            "record_id": "sg-oow-v-003",
        },
        {
            "cert_fp": fps_map["leaf-revoked-byname-deep"],
            "signer_id": "cust-echo",
            "event_ts": "2026-01-25T16:45:00Z",
            "record_id": "sg-oow-v-004",
        },
    ]


def visible_signer_decoys(
    rng: _LCG, fps: list[str], fps_map: dict[str, str]
) -> list[dict[str, str]]:
    """In-window cust-echo / cust-foxtrot rows matching ordinary SIGN shape."""
    decoys: list[dict[str, str]] = []
    echo_ts = (
        "2026-02-10T10:00:00Z",
        "2026-02-14T11:30:00Z",
        "2026-02-18T08:15:00Z",
        "2026-02-22T16:40:00Z",
    )
    fox_ts = (
        "2025-11-05T09:00:00Z",
        "2025-11-18T13:20:00Z",
        "2025-10-28T07:45:00Z",
        "2025-11-25T18:05:00Z",
    )
    for i, ts in enumerate(echo_ts):
        decoys.append(
            {
                "cert_fp": rng.choice(fps),
                "signer_id": "cust-echo",
                "event_ts": ts,
                "record_id": f"sg-dec-e-{i:02d}",
            }
        )
    for i, ts in enumerate(fox_ts):
        decoys.append(
            {
                "cert_fp": rng.choice(fps),
                "signer_id": "cust-foxtrot",
                "event_ts": ts,
                "record_id": f"sg-dec-f-{i:02d}",
            }
        )
    # In-window decoys on trap leaves so grepping the leaf is not enough.
    decoys.extend(
        [
            {
                "cert_fp": fps_map["leaf-multi"],
                "signer_id": "cust-alpha",
                "event_ts": "2026-01-15T08:15:00Z",
                "record_id": "sg-dec-keep-m",
            },
            {
                "cert_fp": fps_map["leaf-accept-a1"],
                "signer_id": "cust-bravo",
                "event_ts": "2026-01-15T09:30:00Z",
                "record_id": "sg-dec-keep-a1",
            },
        ]
    )
    return decoys


def write_journal(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(line + "\n" for line in lines))


def main() -> None:
    fps_map = load_fps()
    cert_fps = sorted(set(fps_map.values()))

    rng_vis = _LCG(RNG_SEED)
    rng_hold = _LCG(RNG_SEED ^ 0xA5A5A5A5)
    rng_decoy = _LCG(RNG_SEED ^ 0x13579BDF)

    visible: list[str] = []
    for rec in CORE_ACCESS:
        if rec["kind"] in ("joined", "fs_only"):
            visible.append(access_line(rec))

    sign_lines = bulk_sign_events(
        rng_vis,
        cert_fps,
        VISIBLE_SIGN_TARGET,
        start_id=1000,
        signer_pool=IN_WINDOW_SIGNERS,
    )

    oow_traps = visible_oow_traps(fps_map)
    cn_of_fp = {fp: cn for cn, fp in fps_map.items()}
    unsafe = sorted(
        {
            cn_of_fp[t["cert_fp"]]
            for t in oow_traps
            if cn_of_fp[t["cert_fp"]] not in SAFE_OOW_TARGETS
        }
    )
    if unsafe:
        raise SystemExit(
            "out-of-window trap targets are not containable at an intermediate: "
            + ", ".join(unsafe)
        )
    oow_inserts = [
        (idx, sign_line(trap))
        for idx, trap in zip(VISIBLE_OOW_INSERT_AT, oow_traps, strict=True)
    ]
    insert_spread(sign_lines, oow_inserts)

    decoys = visible_signer_decoys(rng_decoy, cert_fps, fps_map)
    decoy_indices = (420, 980, 1820, 2588, 3340, 1100, 1950, 2720, 3500, 550)
    decoy_inserts = [
        (idx, sign_line(rec))
        for idx, rec in zip(decoy_indices, decoys, strict=True)
    ]
    insert_spread(sign_lines, decoy_inserts)

    visible.extend(sign_lines)

    held = bulk_sign_events(
        rng_hold,
        cert_fps,
        HELD_SIGN_TARGET - 1,
        start_id=9000,
        signer_pool=IN_WINDOW_SIGNERS,
    )
    # The held-out shard must also be a no-new-cut leaf; the previous choice
    # leaf-accept-deep forced inter-a1 and collapsed expired/not_yet/name_constraint
    # verdicts into revoked, making the reason coverage tests fail.
    # The held-out trap must be a no-new-cut leaf and must not appear in the visible
    # corpus, otherwise a visible-only agent can still discover it. leaf-xc-one fits
    # both constraints and is already rejected, so its verdict is unchanged.
    held_trap = {
        "cert_fp": fps_map["leaf-xc-one"],
        "signer_id": "cust-echo",
        "event_ts": "2026-01-15T12:00:00Z",
        "record_id": "sg-oow-h-001",
    }
    insert_spread(held, [(1750, sign_line(held_trap))])

    write_access_db()
    write_journal(VISIBLE, visible)
    write_journal(HELD_OUT, held)

    vis_sign = sum(1 for ln in visible if ln.startswith("SIGN"))
    hold_sign = sum(1 for ln in held if ln.startswith("SIGN"))
    print(
        f"visible lines={len(visible)} sign={vis_sign} "
        f"access={len(visible) - vis_sign}\n"
        f"held_out lines={len(held)} sign={hold_sign}\n"
        f"visible bytes={VISIBLE.stat().st_size} "
        f"held_out bytes={HELD_OUT.stat().st_size}"
    )


if __name__ == "__main__":
    main()
