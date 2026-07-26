"""Verifier for ambulance-demand freeze-epoch regret invariant YAML."""

from __future__ import annotations

import hashlib
import os
import struct
import subprocess
from pathlib import Path

import pytest
import yaml

OUT = Path("/app/output/invariant.yaml")
ENV = Path("/app/environment")
VERIFY_BIN = Path("/tmp/xdrv_verify")

EXPECT_ARM = "hold_meta"
EXPECT_SEED = 41246
EXPECT_FREEZE = 2


def _zones():
    zones = []
    for p in sorted((ENV / "fixtures" / "zones").glob("*.bin")):
        raw = p.read_bytes()
        assert raw[:4] == b"ZNF1"
        n, fdim, stamp = struct.unpack_from("<HHI", raw, 4)
        off = 12
        for _ in range(n):
            zid, lab = struct.unpack_from("<Hh", raw, off)
            off += 4
            feats = list(struct.unpack_from("<" + "d" * fdim, raw, off))
            off += 8 * fdim
            zones.append((zid, lab, feats, stamp))
    return zones


def _eigengap_rows(zones):
    items = sorted(((sum(f) / len(f), zid, lab, f) for zid, lab, f, _ in zones))
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
    return rows


def _load_base_and_journal():
    base_raw = (ENV / "weights" / "w_base.bin").read_bytes()
    assert base_raw[:4] == b"WB01"
    dim = struct.unpack_from("<H", base_raw, 4)[0]
    off = 6
    w = list(struct.unpack_from("<" + "d" * dim, base_raw, off))
    off += 8 * dim
    b = struct.unpack_from("<d", base_raw, off)[0]

    jraw = (ENV / "weights" / "w_journal.bin").read_bytes()
    assert jraw[:4] == b"WJ01"
    jdim, n = struct.unpack_from("<HI", jraw, 4)
    assert jdim == dim
    off = 10
    updates = []
    for _ in range(n):
        epoch = struct.unpack_from("<I", jraw, off)[0]
        off += 4
        dw = list(struct.unpack_from("<" + "d" * dim, jraw, off))
        off += 8 * dim
        db = struct.unpack_from("<d", jraw, off)[0]
        off += 8
        updates.append((epoch, dw, db))
    return w, b, updates


def _replay(w, b, updates, freeze: int):
    ww = list(w)
    bb = b
    for epoch, dw, db in sorted(updates, key=lambda u: u[0]):
        if epoch <= freeze:
            for i in range(len(ww)):
                ww[i] += dw[i]
            bb += db
    return ww, bb


def _tip_weights():
    raw = (ENV / "weights" / "frozen_w.bin").read_bytes()
    assert raw[:4] == b"FW01"
    dim = struct.unpack_from("<H", raw, 4)[0]
    off = 6
    w = list(struct.unpack_from("<" + "d" * dim, raw, off))
    off += 8 * dim
    b = struct.unpack_from("<d", raw, off)[0]
    return w, b


def _hinge(y: int, s: float) -> float:
    return max(0.0, 1.0 - y * s)


def _regret_milli(rows, w, b) -> int:
    learn = best_pos = best_neg = 0.0
    for _, _, lab, feats, _ in rows:
        s = sum(a * x for a, x in zip(w, feats, strict=False)) + b
        learn += _hinge(lab, s)
        best_pos += _hinge(lab, 1.0)
        best_neg += _hinge(lab, -1.0)
    best = min(best_pos, best_neg)
    n = max(1, len(rows))
    return round(1000.0 * (learn - best) / n)


def _digest(
    kind: str,
    seed: int,
    arm: str,
    cites: list[str],
    regret_milli: int,
    fuzz_rounds: int = 0,
) -> str:
    keys = []
    for c in cites:
        if len(c) >= 5 and c[0] == "z":
            keys.append(c[1:5])
        else:
            keys.append(c)
    keys = sorted(keys)
    payload = f"{kind}|{seed}|{arm}|{','.join(keys)}|{regret_milli}"
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


def _expected():
    zones = _zones()
    rows = _eigengap_rows(zones)
    cites = [r[4] for r in rows]
    base_w, base_b, updates = _load_base_and_journal()
    fw, fb = _replay(base_w, base_b, updates, EXPECT_FREEZE)
    tw, tb = _tip_weights()
    milli = _regret_milli(rows, fw, fb)
    tip_milli = _regret_milli(rows, tw, tb)
    assert milli != tip_milli
    return {
        "cites": cites,
        "regret_milli": milli,
        "tip_regret_milli": tip_milli,
        "seed": EXPECT_SEED,
        "arm": EXPECT_ARM,
        "digest": _digest("cluster", EXPECT_SEED, EXPECT_ARM, cites, milli),
    }


def _run_cli() -> None:
    env = os.environ.copy()
    env["PATH"] = "/usr/local/go/bin:/opt/verifier/bin:" + env.get("PATH", "")
    env.setdefault("GOTOOLCHAIN", "local")
    subprocess.run(
        [
            "go",
            "build",
            "-C",
            "/app/environment",
            "-o",
            str(VERIFY_BIN),
            "./cmd/xdrv",
        ],
        check=True,
        capture_output=True,
        env=env,
    )
    subprocess.run(
        [
            str(VERIFY_BIN),
            "-root",
            "/app/environment",
            "-out",
            "/app/output/invariant.yaml",
            "-arm",
            "1",
        ],
        check=True,
        capture_output=True,
        env=env,
    )


def _load_yaml():
    assert OUT.is_file(), f"missing {OUT}"
    return yaml.safe_load(OUT.read_text())


@pytest.fixture(scope="module")
def expect():
    return _expected()


@pytest.fixture(scope="module")
def doc(expect):
    if not OUT.is_file():
        _run_cli()
    return _load_yaml()


def _row(doc):
    assert doc.get("schema") == "demand-invariant-v1"
    rows = doc.get("rows") or []
    assert rows, "no rows"
    return rows[0]


def test_a1_zn_layout(doc, expect):
    """Eigengap packing produces both partitions in contract order."""
    row = _row(doc)
    cites = row.get("cites") or []
    assert cites == expect["cites"]
    got_parts = {c[-2:] for c in cites}
    assert "00" in got_parts
    assert "01" in got_parts


def test_a2_zn_cache_stamp(doc, expect):
    """Warm cache after first eval must still match eigengap cites."""
    cache = (ENV / "data" / "part_cache.bin").read_bytes()
    assert cache[:4] == b"PC01"
    stamp = struct.unpack_from("<I", cache, 4)[0]
    freeze = struct.unpack_from("<I", cache, 8)[0]
    zones = _zones()
    max_stamp = max(z[3] for z in zones)
    assert stamp == max_stamp
    assert freeze == EXPECT_FREEZE
    row = _row(doc)
    assert (row.get("cites") or []) == expect["cites"]


def test_a3_zn_flip(doc, expect):
    """Partition ids are exactly {0,1} under the cut rule."""
    _ = expect
    row = _row(doc)
    tags = row.get("cites") or []
    parts = sorted({int(t[-2:], 16) for t in tags})
    assert parts == [0, 1]


def test_a4_zn_side(doc, expect):
    """Active arm and partition-1 cites are present."""
    row = _row(doc)
    assert row["arm"] == expect["arm"]
    assert any(t[-3:] == "p01" for t in (row.get("cites") or []))


def test_b1_rg_freeze_unit(doc, expect):
    """Regret must match freeze-epoch replay, not the tip snapshot."""
    row = _row(doc)
    assert int(row["regret_milli"]) == expect["regret_milli"]
    assert int(row["regret_milli"]) != expect["tip_regret_milli"]


def test_b2_rg_lane(doc, expect):
    """Held-out meta arm carries freeze-epoch regret."""
    row = _row(doc)
    assert row["arm"] == "hold_meta"
    assert int(row["regret_milli"]) == expect["regret_milli"]


def test_b3_rg_flip(doc, expect):
    """Regret is strictly positive under freeze weights."""
    row = _row(doc)
    assert int(row["regret_milli"]) > 0
    assert int(row["regret_milli"]) == expect["regret_milli"]


def test_b4_rg_side(doc, expect):
    """Tip snapshot divergence is observable but must not be emitted."""
    row = _row(doc)
    assert expect["tip_regret_milli"] != expect["regret_milli"]
    assert int(row["regret_milli"]) == expect["regret_milli"]
    assert row["arm"] == "hold_meta"


def test_c1_mt_roc(doc, expect):
    """Cluster metamorphic digest binds freeze-epoch regret and cites."""
    row = _row(doc)
    cites = row.get("cites") or []
    got = _digest(
        "cluster", int(doc["seed"]), row["arm"], cites, int(row["regret_milli"])
    )
    assert row["meta_digest"] == got
    assert got == expect["digest"]


def test_c2_mt_slot(doc, expect):
    """Seed and arm match the pinned held-out meta arm."""
    assert int(doc["seed"]) == expect["seed"]
    row = _row(doc)
    assert row["arm"] == "hold_meta"


def test_c3_mt_flip(doc, expect):
    """Digest width and recomputation survive tip/weight confusion."""
    row = _row(doc)
    assert len(row["meta_digest"]) == 16
    cites = row.get("cites") or []
    tip_dig = _digest(
        "cluster",
        int(doc["seed"]),
        row["arm"],
        cites,
        expect["tip_regret_milli"],
    )
    got = _digest(
        "cluster", int(doc["seed"]), row["arm"], cites, int(row["regret_milli"])
    )
    assert row["meta_digest"] == got
    assert row["meta_digest"] != tip_dig


def test_c4_mt_side(doc, expect):
    """Fuzz lane digest is well-formed; primary digest remains cluster."""
    _ = expect
    row = _row(doc)
    cites = row.get("cites") or []
    got = _digest(
        "fuzz", 61474, row["arm"], cites, int(row["regret_milli"]), fuzz_rounds=5
    )
    assert len(got) == 16
    cluster = _digest(
        "cluster", int(doc["seed"]), row["arm"], cites, int(row["regret_milli"])
    )
    assert row["meta_digest"] == cluster


def test_d1_yv_cite(doc, expect):
    """Primary cite is a packed tag present in cites."""
    _ = expect
    row = _row(doc)
    cite = row["cite"]
    assert isinstance(cite, str)
    assert cite.startswith("z")
    assert "p" in cite
    assert cite in (row.get("cites") or [])
    assert cite != "MISSING"


def test_d2_yv_bind(doc, expect):
    """part_tag binds cite suffix; digest and regret are typed observations."""
    _ = expect
    row = _row(doc)
    cites = row.get("cites") or []
    assert row["cite"] in cites
    assert row["part_tag"] == row["cite"][-4:]
    assert isinstance(row["meta_digest"], str)
    assert len(row["meta_digest"]) == 16
    assert isinstance(row["regret_milli"], int)


def test_d3_yv_flip(doc, expect):
    """Single schema header; tip residue must not append duplicate docs."""
    _ = expect
    text = OUT.read_text()
    schema_lines = [
        ln for ln in text.splitlines() if ln.startswith("schema: demand-invariant-v1")
    ]
    assert len(schema_lines) == 1
    row = _row(doc)
    assert "cites" in row
    assert len(row["cites"]) >= 1


def test_d4_yv_twice(doc, expect):
    """Consecutive evaluations are byte-identical under warm cache + tip reset."""
    _ = doc
    first = OUT.read_bytes()
    _run_cli()
    second = OUT.read_bytes()
    assert first == second
    schema_lines = [
        ln
        for ln in first.splitlines()
        if ln.startswith(b"schema: demand-invariant-v1")
    ]
    assert len(schema_lines) == 1
    row = yaml.safe_load(second)["rows"][0]
    assert row["cites"] == expect["cites"]
    assert int(row["regret_milli"]) == expect["regret_milli"]
