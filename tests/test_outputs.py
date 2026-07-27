"""Verifier for bed-occupancy effect-lattice proof log."""

from __future__ import annotations

import hashlib
import json
import struct
import subprocess
from pathlib import Path

import pytest

OUT = Path("/app/output/invariant_proof_log.json")
ROOT = Path("/app/environment")
VERIFY_BIN = Path("/tmp/bn_run_verify")


def _tag(id_: int, sc: float, seed: int, arm_ix: int) -> str:
    payload = f"id={id_}|sc={sc:.6f}|seed={seed}|arm={arm_ix}".encode()
    return hashlib.sha256(payload).hexdigest()[:12]


def _load_feat(path: Path):
    raw = path.read_bytes()
    assert raw[:4] == b"FEAT"
    n, nf, _stamp = struct.unpack_from("<HHI", raw, 4)
    off = 12
    rows = []
    for _ in range(n):
        id_, role, _pad = struct.unpack_from("<HBB", raw, off)
        off += 4
        feats = []
        for _j in range(nf):
            (f,) = struct.unpack_from("<d", raw, off)
            off += 8
            feats.append(f)
        a, b, lim = struct.unpack_from("<hhH", raw, off)
        off += 6
        rows.append({"id": id_, "role": role, "feats": feats, "a": a, "b": b, "lim": lim})
    return rows


def _load_pin(path: Path):
    raw = path.read_bytes()
    assert raw[:4] == b"PIN1"
    slice_id, seed = struct.unpack_from("<HI", raw, 4)
    (nc,) = struct.unpack_from("<H", raw, 10)
    order = list(struct.unpack_from("<" + "H" * nc, raw, 12))
    return {"slice": slice_id, "seed": seed, "order": order}


def _load_wts(path: Path):
    raw = path.read_bytes()
    assert raw[:4] == b"WB01"
    (dim,) = struct.unpack_from("<H", raw, 4)
    off = 6
    w = []
    for _ in range(dim):
        (f,) = struct.unpack_from("<d", raw, off)
        off += 8
        w.append(f)
    (bias,) = struct.unpack_from("<d", raw, off)
    return w, bias


def _load_arms(path: Path):
    arms = []
    cur = None
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "[[arm]]":
            if cur:
                arms.append(cur)
            cur = {}
            continue
        if cur is None or "=" not in line:
            continue
        k, v = [x.strip() for x in line.split("=", 1)]
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1]
        if k in ("seed", "jump", "rotate"):
            cur[k] = int(v)
        else:
            cur[k] = v
    if cur:
        arms.append(cur)
    return arms


def _score(feats, w, bias):
    return sum(a * b for a, b in zip(w, feats)) + bias


def _expect_metrics():
    rows = {r["id"]: r for r in _load_feat(ROOT / "fixtures" / "feat_blob.bin")}
    pin = _load_pin(ROOT / "data" / "pin_s.lock")
    w, bias = _load_wts(ROOT / "weights" / "w_blob.bin")
    arms = _load_arms(ROOT / "data" / "xtra_clk.toml")
    assert pin["slice"] == 3
    metrics = []
    primary_seed = None
    for arm_ix, arm in enumerate(arms):
        if arm.get("kind") != "hold":
            continue
        if primary_seed is None:
            primary_seed = arm["seed"]
        tags = []
        wtags = []
        ka = kb = lim = 0
        for id_ in pin["order"]:
            r = rows[id_]
            sc = _score(r["feats"], w, bias)
            tg = _tag(id_, sc, arm["seed"], arm_ix)
            tags.append(tg)
            if r["role"] != 0:
                continue
            wtags.append(tg)
            ka += r["a"]
            kb += r["b"]
            lim += r["lim"]
        wsorted = sorted(wtags)
        lat = hashlib.sha256(
            f"lat|{','.join(wsorted)}|{ka}|{kb}|{lim}".encode()
        ).hexdigest()[:16]
        jump = int(arm["jump"])
        a2 = (ka + jump) % lim if lim else ka
        b2 = lim - a2
        jmp = hashlib.sha256(
            f"jmp|{arm['name']}|{arm['seed']}|{a2}|{b2}|{lim}|{lat}|{arm['rotate']}".encode()
        ).hexdigest()[:16]
        uk = hashlib.sha256(f"unit|{lat}|{arm['name']}".encode()).hexdigest()[:16]
        cite = wtags[0]
        metrics.append(
            {
                "arm": arm["name"],
                "score_tag": cite,
                "lat_hex": lat,
                "jmp_hex": jmp,
                "a_cnt": a2,
                "b_cnt": b2,
                "z_lim": lim,
                "unit_key": uk,
                "cite": cite,
            }
        )
    metrics.sort(key=lambda m: m["arm"])
    return {"schema": "occ-proof-v1", "slice": 3, "seed": primary_seed, "metrics": metrics}


def _run_cli() -> None:
    subprocess.run(
        [
            "go",
            "build",
            "-C",
            "/app/environment",
            "-o",
            str(VERIFY_BIN),
            "/app/environment/cmd/bn_run",
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            str(VERIFY_BIN),
            "-root",
            "/app/environment",
            "-out",
            "/app/output/invariant_proof_log.json",
        ],
        check=True,
        capture_output=True,
    )


@pytest.fixture(scope="module")
def expect():
    return _expect_metrics()


@pytest.fixture(scope="module")
def doc(expect):
    if not OUT.is_file():
        _run_cli()
    data = json.loads(OUT.read_text())
    return data


def _by_arm(doc):
    return {m["arm"]: m for m in doc.get("metrics") or []}


def test_a1_sc_layout(doc, expect):
    """Contract observation check."""
    got = _by_arm(doc)
    exp = _by_arm(expect)
    assert set(got) == set(exp)
    for arm, row in exp.items():
        assert got[arm]["score_tag"] == row["score_tag"]
        assert got[arm]["cite"] == row["cite"]


def test_a2_sc_rng(doc, expect):
    """Contract observation check."""
    assert int(doc["seed"]) == int(expect["seed"])
    row = _by_arm(doc)["hold_rot_a"]
    assert row["score_tag"] == _by_arm(expect)["hold_rot_a"]["score_tag"]


def test_a3_sc_flip(doc, expect):
    """Contract observation check."""
    a = _by_arm(doc)["hold_rot_a"]["score_tag"]
    b = _by_arm(doc)["hold_clk_b"]["score_tag"]
    assert a != b
    assert a == _by_arm(expect)["hold_rot_a"]["score_tag"]


def test_a4_sc_arm(doc, expect):
    """Contract observation check."""
    for arm in ("hold_rot_a", "hold_clk_b"):
        assert _by_arm(doc)[arm]["score_tag"] == _by_arm(expect)[arm]["score_tag"]


def test_b1_lt_unit(doc, expect):
    """Contract observation check."""
    for arm, row in _by_arm(expect).items():
        assert _by_arm(doc)[arm]["lat_hex"] == row["lat_hex"]


def test_b2_lt_gate(doc, expect):
    """Contract observation check."""
    for arm, row in _by_arm(doc).items():
        a_cnt = row["a_cnt"]
        b_cnt = row["b_cnt"]
        z_lim = row["z_lim"]
        assert a_cnt + b_cnt == z_lim
        assert z_lim == _by_arm(expect)[arm]["z_lim"]


def test_b3_lt_flip(doc, expect):
    """Contract observation check."""
    for arm, row in _by_arm(expect).items():
        assert _by_arm(doc)[arm]["z_lim"] == row["z_lim"]


def test_b4_lt_arm(doc, expect):
    """Contract observation check."""
    for arm, row in _by_arm(doc).items():
        a_cnt = row["a_cnt"]
        b_cnt = row["b_cnt"]
        z_lim = row["z_lim"]
        assert a_cnt + b_cnt == z_lim
        assert _by_arm(doc)[arm]["lat_hex"] == _by_arm(expect)[arm]["lat_hex"]


def test_c1_jw_reb(doc, expect):
    """Contract observation check."""
    for arm, row in _by_arm(expect).items():
        assert _by_arm(doc)[arm]["jmp_hex"] == row["jmp_hex"]
        assert _by_arm(doc)[arm]["a_cnt"] == row["a_cnt"]


def test_c2_jw_gap(doc, expect):
    """Contract observation check."""
    for arm, row in _by_arm(expect).items():
        got = _by_arm(doc)[arm]
        a_cnt = got["a_cnt"]
        b_cnt = got["b_cnt"]
        z_lim = got["z_lim"]
        assert a_cnt == row["a_cnt"]
        assert b_cnt == row["b_cnt"]
        assert a_cnt + b_cnt == z_lim


def test_c3_jw_flip(doc, expect):
    """Contract observation check."""
    a = _by_arm(doc)["hold_rot_a"]["jmp_hex"]
    b = _by_arm(doc)["hold_clk_b"]["jmp_hex"]
    assert a != b
    assert a == _by_arm(expect)["hold_rot_a"]["jmp_hex"]


def test_c4_jw_arm(doc, expect):
    """Contract observation check."""
    for arm in ("hold_rot_a", "hold_clk_b"):
        assert _by_arm(doc)[arm]["jmp_hex"] == _by_arm(expect)[arm]["jmp_hex"]


def test_d1_em_shape(doc, expect):
    """Contract observation check."""
    assert doc.get("schema") == "occ-proof-v1"
    assert int(doc.get("slice")) == 3
    assert len(doc.get("metrics") or []) == len(expect["metrics"])
    for row in doc["metrics"]:
        for key in ("arm", "score_tag", "lat_hex", "jmp_hex", "a_cnt", "b_cnt", "z_lim", "unit_key", "cite"):
            assert key in row


def test_d2_em_cite(doc, expect):
    """Contract observation check."""
    for arm, row in _by_arm(expect).items():
        got = _by_arm(doc)[arm]
        assert got["cite"] == got["score_tag"] == row["cite"]
        assert got["lat_hex"] == row["lat_hex"]
        assert got["unit_key"] == row["unit_key"]
        assert got["jmp_hex"] == row["jmp_hex"]


def test_d3_em_flip(doc, expect):
    """Contract observation check."""
    for arm, row in _by_arm(expect).items():
        assert _by_arm(doc)[arm]["unit_key"] == row["unit_key"]


def test_d4_em_twice(doc, expect):
    """Contract observation check."""
    first = OUT.read_bytes()
    _run_cli()
    second = OUT.read_bytes()
    assert first == second
    data = json.loads(first)
    assert data.get("schema") == "occ-proof-v1"
    assert len(data.get("metrics") or []) == 2
