"""Rebuild offline ambulance-demand evaluation fixtures (authoring helper)."""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def mean(feats: list[float]) -> float:
    return sum(feats) / len(feats)


def hinge(y: int, s: float) -> float:
    return max(0.0, 1.0 - y * s)


def pack_zones() -> tuple[list[tuple[int, int, list[float]]], int]:
    # (zone_id, label, feats) — same geometry as prior corpus; stamp is authoritative.
    stamp = 0x00A11CE0
    zones = [
        (1, 1, [1.0, 0.2, 0.1]),
        (2, 1, [0.9, 0.3, 0.2]),
        (3, -1, [1.2, 0.1, 0.0]),
        (4, 1, [2.8, 0.4, 0.5]),
        (5, -1, [3.0, 0.5, 0.4]),
        (6, -1, [8.5, 0.8, 0.3]),
        (7, 1, [9.2, 1.1, 0.1]),
        (8, 1, [9.0, 1.0, 0.2]),
    ]
    zdir = ROOT / "fixtures" / "zones"
    zdir.mkdir(parents=True, exist_ok=True)
    groups = {
        "basin_a.bin": zones[0:3],
        "basin_b.bin": zones[3:5],
        "channel_c.bin": zones[5:8],
    }
    for name, recs in groups.items():
        body = bytearray()
        body += b"ZNF1"
        body += struct.pack("<HHI", len(recs), 3, stamp)
        for zid, lab, feats in recs:
            body += struct.pack("<Hh", zid, lab)
            for v in feats:
                body += struct.pack("<d", float(v))
        (zdir / name).write_bytes(body)
    return zones, stamp


def eigengap_rows(zones: list[tuple[int, int, list[float]]]):
    items = sorted(((mean(f), zid, lab, f) for zid, lab, f in zones))
    best_gap, cut_after = -1.0, 0
    for i in range(len(items) - 1):
        g = items[i + 1][0] - items[i][0]
        if g > best_gap:
            best_gap, cut_after = g, i + 1
    rows = []
    for i, (_, zid, lab, f) in enumerate(items):
        part = 0 if i < cut_after else 1
        tag = f"z{zid:04x}p{part:02x}"
        rows.append((part, zid, lab, f, tag))
    rows.sort(key=lambda r: (r[0], r[1]))
    return rows, cut_after


def write_weights_and_journal(base_w: list[float], base_b: float):
    wdir = ROOT / "weights"
    wdir.mkdir(parents=True, exist_ok=True)
    dim = len(base_w)

    # Base checkpoint (start of journal).
    base = bytearray(b"WB01")
    base += struct.pack("<H", dim)
    for v in base_w:
        base += struct.pack("<d", v)
    base += struct.pack("<d", base_b)
    (wdir / "w_base.bin").write_bytes(base)

    # Journal updates after freeze epoch 2 — tip diverges from freeze.
    updates = [
        (1, [0.0, 0.0, 0.0], 0.0),
        (2, [0.0, 0.0, 0.0], 0.0),
        (3, [0.35, 0.20, -0.15], 0.40),
        (4, [0.25, 0.15, -0.05], 0.20),
        (5, [0.10, 0.05, 0.00], 0.10),
    ]
    j = bytearray(b"WJ01")
    j += struct.pack("<HI", dim, len(updates))
    for epoch, dw, db in updates:
        j += struct.pack("<I", epoch)
        for v in dw:
            j += struct.pack("<d", v)
        j += struct.pack("<d", db)
    (wdir / "w_journal.bin").write_bytes(j)

    # Tip snapshot = base + all updates (not used for held-out freeze scoring).
    tip_w = list(base_w)
    tip_b = base_b
    for _, dw, db in updates:
        for i in range(dim):
            tip_w[i] += dw[i]
        tip_b += db
    tip = bytearray(b"FW01")
    tip += struct.pack("<H", dim)
    for v in tip_w:
        tip += struct.pack("<d", v)
    tip += struct.pack("<d", tip_b)
    (wdir / "frozen_w.bin").write_bytes(tip)
    return tip_w, tip_b, updates


def replay(base_w, base_b, updates, freeze_epoch: int):
    w = list(base_w)
    b = base_b
    for epoch, dw, db in sorted(updates, key=lambda u: u[0]):
        if epoch <= freeze_epoch:
            for i in range(len(w)):
                w[i] += dw[i]
            b += db
    return w, b


def regret_milli(rows, w, b) -> int:
    learn = best_pos = best_neg = 0.0
    for _, _, lab, feats, _ in rows:
        s = sum(a * x for a, x in zip(w, feats, strict=False)) + b
        learn += hinge(lab, s)
        best_pos += hinge(lab, 1.0)
        best_neg += hinge(lab, -1.0)
    best = min(best_pos, best_neg)
    n = max(1, len(rows))
    return round(1000.0 * (learn - best) / n)


def write_split():
    # SPL2: name[16], kind u8, seed u32, freeze_epoch u32
    arms = [
        ("train_core", 0, 20973, 5),
        ("hold_meta", 1, 41246, 2),
        ("hold_fuzz", 1, 61474, 2),
    ]
    body = bytearray(b"SPL2")
    body += struct.pack("<H", len(arms))
    for name, kind, seed, fr in arms:
        nb = name.encode()[:16].ljust(16, b"\x00")
        body += nb
        body += struct.pack("<B", kind)
        body += struct.pack("<I", seed)
        body += struct.pack("<I", fr)
    (ROOT / "data" / "pinned_split.lock").write_bytes(body)


def write_stale_cache() -> None:
    # Stale cache: wrong stamp and all-partition-0 tags (pre-eigengap residue).
    cites = [f"z{i:04x}p00" for i in range(1, 9)]
    body = bytearray(b"PC01")
    body += struct.pack("<IIH", 0xDEADBEEF, 5, len(cites))
    for c in cites:
        cb = c.encode()[:12].ljust(12, b"\x00")
        body += cb
    (ROOT / "data" / "part_cache.bin").write_bytes(body)
    tip = bytearray(b"TIP1")
    tip += struct.pack("<i", 0)
    tip += b"stale_pack_fp\x00\x00"
    tip += struct.pack("<i", 0)
    tip += b"stale_w_fp\x00\x00\x00\x00"
    tip += struct.pack("<i", 0)
    tip += b"stale_rg_fp\x00\x00\x00"
    (ROOT / "data" / "run_tip.bin").write_bytes(tip)


def digest(
    kind: str, seed: int, arm: str, cites: list[str], milli: int, fuzz_rounds: int = 0
) -> str:
    keys = sorted(c[1:5] if len(c) >= 5 and c[0] == "z" else c for c in cites)
    payload = f"{kind}|{seed}|{arm}|{','.join(keys)}|{milli}"
    if kind == "cluster":
        payload = "C:" + payload
    elif kind == "feature":
        payload = "F:" + payload
    elif kind == "stream":
        payload = "S:" + payload
    elif kind == "fuzz":
        payload = f"Z:{fuzz_rounds}:{payload}"
    else:
        payload = "X:" + payload
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def main() -> None:
    zones, stamp = pack_zones()
    rows, cut = eigengap_rows(zones)
    base_w = [0.5, -0.25, 0.1]
    base_b = 0.05
    tip_w, tip_b, updates = write_weights_and_journal(base_w, base_b)
    freeze_w, freeze_b = replay(base_w, base_b, updates, freeze_epoch=2)
    write_split()
    write_stale_cache()

    cites = [r[4] for r in rows]
    milli_freeze = regret_milli(rows, freeze_w, freeze_b)
    milli_tip = regret_milli(rows, tip_w, tip_b)
    dig = digest("cluster", 41246, "hold_meta", cites, milli_freeze)

    print("stamp", hex(stamp), "cut_after", cut)
    print("cites", cites)
    print("freeze_w", freeze_w, "freeze_b", freeze_b, "milli_freeze", milli_freeze)
    print("tip_w", tip_w, "tip_b", tip_b, "milli_tip", milli_tip)
    print("cluster_digest", dig)
    assert milli_freeze != milli_tip, "tip must diverge from freeze for hardness"
    assert milli_freeze == 533


if __name__ == "__main__":
    main()
