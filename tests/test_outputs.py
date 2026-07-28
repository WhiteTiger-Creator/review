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
_WARM_MARK = ROOT / "data" / "shadow_warm.bin"
_ROW_CACHE = ROOT / "data" / "row_scores.bin"
_PART_CACHE = ROOT / "data" / "part_cache.bin"
_ARMS_TOML = ROOT / "data" / "xtra_clk.toml"


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


def _feat_stamp() -> int:
    raw = (ROOT / "fixtures" / "feat_blob.bin").read_bytes()
    return struct.unpack_from("<I", raw, 8)[0]


def _part_stamp() -> int:
    return struct.unpack_from("<I", _PART_CACHE.read_bytes(), 4)[0]


def _epoch_matches_feat() -> bool:
    raw = (ROOT / "data" / "run_epoch.bin").read_bytes()
    if len(raw) < 10 or raw[:4] != b"RN01":
        return False
    stamp = struct.unpack_from("<I", raw, 4)[0]
    slice_id = struct.unpack_from("<H", raw, 8)[0]
    return stamp == _feat_stamp() and slice_id == 3


def _tip_journal_gen() -> int:
    tip = ROOT / "data" / ".tip_snap"
    if not tip.exists():
        return 0
    try:
        return int(json.loads(tip.read_text()).get("gen") or 0)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return 0


def test_a1_sc_layout(doc, expect):
    """Verify score_tag and cite match pin-order write tags for every held-out arm."""
    got = _by_arm(doc)
    exp = _by_arm(expect)
    assert set(got) == set(exp)
    for arm, row in exp.items():
        assert got[arm]["score_tag"] == row["score_tag"]
        assert got[arm]["cite"] == row["cite"]


def test_a2_sc_rng(doc, expect):
    """Verify top-level seed equals hold_rot_a arm seed and its score_tag."""
    assert "seed" in doc
    assert int(doc["seed"]) == int(expect["seed"]) == 4242
    row = _by_arm(doc)["hold_rot_a"]
    assert row["score_tag"] == _by_arm(expect)["hold_rot_a"]["score_tag"]


def test_a3_sc_flip(doc, expect):
    """Verify hold_rot_a and hold_clk_b score tags differ under distinct arm seeds."""
    a = _by_arm(doc)["hold_rot_a"]["score_tag"]
    b = _by_arm(doc)["hold_clk_b"]["score_tag"]
    assert a != b
    assert a == _by_arm(expect)["hold_rot_a"]["score_tag"]


def test_a4_sc_arm(doc, expect):
    """Verify both held-out arms emit the expected opaque score tags."""
    for arm in ("hold_rot_a", "hold_clk_b"):
        assert _by_arm(doc)[arm]["score_tag"] == _by_arm(expect)[arm]["score_tag"]


def test_b1_lt_unit(doc, expect):
    """Verify lat_hex matches role-gated lattice digest for every arm."""
    for arm, row in _by_arm(expect).items():
        assert _by_arm(doc)[arm]["lat_hex"] == row["lat_hex"]


def test_b2_lt_gate(doc, expect):
    """Verify a_cnt + b_cnt == z_lim occupancy conservation for all arms."""
    for arm, row in _by_arm(doc).items():
        a_cnt = row["a_cnt"]
        b_cnt = row["b_cnt"]
        z_lim = row["z_lim"]
        assert a_cnt + b_cnt == z_lim
        assert z_lim == _by_arm(expect)[arm]["z_lim"]


def test_b3_lt_flip(doc, expect):
    """Verify z_lim capacity aggregates match expected write-lane lim sums."""
    for arm, row in _by_arm(expect).items():
        assert _by_arm(doc)[arm]["z_lim"] == row["z_lim"]


def test_b4_lt_arm(doc, expect):
    """Verify conservation and lat_hex jointly for each held-out arm."""
    for arm, row in _by_arm(doc).items():
        a_cnt = row["a_cnt"]
        b_cnt = row["b_cnt"]
        z_lim = row["z_lim"]
        assert a_cnt + b_cnt == z_lim
        assert _by_arm(doc)[arm]["lat_hex"] == _by_arm(expect)[arm]["lat_hex"]


def test_c1_jw_reb(doc, expect):
    """Verify jump rebinding digests and a_cnt after clock discontinuity."""
    for arm, row in _by_arm(expect).items():
        assert _by_arm(doc)[arm]["jmp_hex"] == row["jmp_hex"]
        assert _by_arm(doc)[arm]["a_cnt"] == row["a_cnt"]


def test_c2_jw_gap(doc, expect):
    """Verify post-jump a_cnt/b_cnt pair and conservation gap closure."""
    for arm, row in _by_arm(expect).items():
        got = _by_arm(doc)[arm]
        a_cnt = got["a_cnt"]
        b_cnt = got["b_cnt"]
        z_lim = got["z_lim"]
        assert a_cnt == row["a_cnt"]
        assert b_cnt == row["b_cnt"]
        assert a_cnt + b_cnt == z_lim


def test_c3_jw_flip(doc, expect):
    """Verify jmp_hex differs across held-out arms with distinct jumps."""
    a = _by_arm(doc)["hold_rot_a"]["jmp_hex"]
    b = _by_arm(doc)["hold_clk_b"]["jmp_hex"]
    assert a != b
    assert a == _by_arm(expect)["hold_rot_a"]["jmp_hex"]


def test_c4_jw_arm(doc, expect):
    """Verify both arms emit the expected jmp_hex digests."""
    for arm in ("hold_rot_a", "hold_clk_b"):
        assert _by_arm(doc)[arm]["jmp_hex"] == _by_arm(expect)[arm]["jmp_hex"]


def test_d1_em_shape(doc, expect):
    """Verify top-level schema, slice=3, seed, and metrics row field presence."""
    assert doc.get("schema") == "occ-proof-v1"
    assert "slice" in doc and int(doc.get("slice")) == 3
    assert "seed" in doc and int(doc.get("seed")) == int(expect["seed"])
    assert len(doc.get("metrics") or []) == len(expect["metrics"])
    for row in doc["metrics"]:
        for key in ("arm", "score_tag", "lat_hex", "jmp_hex", "a_cnt", "b_cnt", "z_lim", "unit_key", "cite"):
            assert key in row


def test_d2_em_cite(doc, expect):
    """Verify cite equals score_tag and lattice/jump/unit digests match."""
    for arm, row in _by_arm(expect).items():
        got = _by_arm(doc)[arm]
        assert got["cite"] == got["score_tag"] == row["cite"]
        assert got["lat_hex"] == row["lat_hex"]
        assert got["unit_key"] == row["unit_key"]
        assert got["jmp_hex"] == row["jmp_hex"]


def test_d3_em_flip(doc, expect):
    """Verify unit_key digests match for every held-out arm."""
    for arm, row in _by_arm(expect).items():
        assert _by_arm(doc)[arm]["unit_key"] == row["unit_key"]


def test_d4_em_twice(doc, expect):
    """Verify byte-identical reruns after warm-shadow and scored-row residue."""
    first = OUT.read_bytes()
    _WARM_MARK.write_bytes(b"warm\n")
    _ROW_CACHE.write_bytes(b"ROW1" + b"\x00" * 16)
    _run_cli()
    second = OUT.read_bytes()
    assert first == second
    data = json.loads(first)
    assert data.get("schema") == "occ-proof-v1"
    assert int(data.get("slice")) == 3
    assert "seed" in data
    assert len(data.get("metrics") or []) == 2
    assert _PART_CACHE.exists()
    stamp = _part_stamp()
    assert stamp == _feat_stamp()
    assert stamp != 0xDEADBEEF
    assert _tip_journal_gen() > 0
    assert _epoch_matches_feat()


def test_e1_jump_perturb(doc, expect):
    """Changing hold_clk_b jump must move its jmp_hex; hold_rot_a stays fixed."""
    baseline = _by_arm(expect)
    original = _ARMS_TOML.read_text()
    assert "hold_clk_b" in original
    try:
        lines = original.splitlines(keepends=True)
        out = []
        in_clk = False
        for line in lines:
            if line.strip() == "[[arm]]":
                in_clk = False
            if "hold_clk_b" in line and "name" in line:
                in_clk = True
            if in_clk and line.strip().startswith("jump"):
                nl = "\n" if line[-1:] == "\n" else ""
                out.append("jump = 9" + nl)
                continue
            out.append(line)
        _ARMS_TOML.write_text("".join(out))
        # Poison PC01 so a stale stamp cannot mask the jump change.
        if _PART_CACHE.exists():
            raw = _PART_CACHE.read_bytes()
            if len(raw) >= 12:
                poisoned = b"PC01" + struct.pack("<I", 0xDEADBEEF) + raw[8:]
                _PART_CACHE.write_bytes(poisoned)
        perturbed = _expect_metrics()
        by_exp = _by_arm(perturbed)
        assert by_exp["hold_clk_b"]["jmp_hex"] != baseline["hold_clk_b"]["jmp_hex"]
        assert by_exp["hold_clk_b"]["a_cnt"] != baseline["hold_clk_b"]["a_cnt"]
        assert by_exp["hold_rot_a"]["jmp_hex"] == baseline["hold_rot_a"]["jmp_hex"]
        assert by_exp["hold_rot_a"]["score_tag"] == baseline["hold_rot_a"]["score_tag"]
        _run_cli()
        doc2 = json.loads(OUT.read_text())
        by = _by_arm(doc2)
        for arm, m in by_exp.items():
            assert by[arm]["jmp_hex"] == m["jmp_hex"]
            assert by[arm]["a_cnt"] == m["a_cnt"]
            assert by[arm]["score_tag"] == m["score_tag"]
        assert _part_stamp() == _feat_stamp()
    finally:
        _ARMS_TOML.write_text(original)
        _run_cli()
