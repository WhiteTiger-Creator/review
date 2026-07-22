#!/usr/bin/env python3
"""Domain checks for trial-site-label-shift-gate-java."""

import json
import subprocess
from pathlib import Path

import pytest

ENV = Path("/app/environment")
OUT = Path("/app/output/gate_ledger.json")


def _rebuild():
    subprocess.run(
        ["mvn", "-q", "-f", "/app/environment/pom.xml", "package"],
        check=True,
        cwd="/app",
    )


def _run_jar():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["java", "-jar", "/app/environment/target/marlin-engine.jar", "--lane", "chrono"],
        check=True,
        cwd="/app",
    )


def _regen():
    if OUT.exists():
        OUT.unlink()
    _rebuild()
    _run_jar()
    return json.loads(OUT.read_text(encoding="utf-8"))


def _u16(raw, off):
    return raw[off] | (raw[off + 1] << 8)


def _i16(raw, off):
    v = _u16(raw, off)
    return v - 0x10000 if v >= 0x8000 else v


def _load_tlf(path):
    raw = path.read_bytes()
    assert raw[:4] == b"TLF1"
    count = _u16(raw, 4)
    off = 6
    recs = []
    for _ in range(count):
        id_len = raw[off]
        off += 1
        pid = raw[off : off + id_len].decode("ascii")
        off += id_len
        sa = _u16(raw, off)
        sb = _u16(raw, off + 2)
        off += 4
        n = raw[off]
        off += 1
        feats = []
        for _j in range(n):
            feats.append(_i16(raw, off))
            off += 2
        width = raw[off]
        off += 1
        hist = raw[off : off + width]
        off += width
        recs.append({"id": pid, "sa": sa, "sb": sb, "feats": feats, "hist": hist})
    return recs


def _rows_by(sheet, pair_id, side):
    return [
        r
        for r in sheet["rank_rows"]
        if r["pair_id"] == pair_id and r["side"] == side
    ]


def _mirror(pid):
    return pid[:-1] if pid[-1:] == "m" else pid + "m"


def _is_mirror(pid):
    return pid[-1:] == "m"


def _hex_to_bytes(hex_str):
    out = bytearray()
    i = 0
    while i < len(hex_str):
        out.append(int(hex_str[i : i + 2], 16))
        i += 2
    return bytes(out)


@pytest.fixture(scope="module")
def sheet():
    return _regen()


def test_tsg_u01_mesh(sheet):
    """Mirrored site pairs must agree after chrono feature cut."""
    bases = sorted(
        {
            r["pair_id"][:-1] if _is_mirror(r["pair_id"]) else r["pair_id"]
            for r in sheet["rank_rows"]
            if r["pack"] == "a2_blob_01" and not _is_mirror(r["pair_id"])
        }
    )
    assert bases, "expected a2 rank rows"
    for base in bases:
        for side, mirror_side in (("a", "b"), ("b", "a")):
            left = _rows_by(sheet, base, side)
            right = _rows_by(sheet, _mirror(base), mirror_side)
            assert left and right
            for a, b in zip(left, right):
                assert a["site_nib"] == b["site_nib"]
                assert a["slot_ok"] == b["slot_ok"]
                assert (a["win_lo"], a["win_hi"]) == (b["win_lo"], b["win_hi"])


def test_tsg_u02_twin(sheet):
    """Twin layouts keep equal windows across mirrored sides."""
    for row in sheet["rank_rows"]:
        if row["pack"] != "a2_blob_01" or _is_mirror(row["pair_id"]):
            continue
        twin = _rows_by(sheet, _mirror(row["pair_id"]), "b" if row["side"] == "a" else "a")
        assert twin and twin[0]["win_lo"] == row["win_lo"] and twin[0]["win_hi"] == row["win_hi"]


def test_tsg_u03_nib(sheet):
    """Terminal hist nibble round-trips through packing into site_nib."""
    pack_names = ["a2_blob_01", "b7_byte_02", "c8_ln_03"]
    packs = {
        name: _load_tlf(ENV / "packs" / (name + ".tlf")) for name in pack_names
    }
    by_id = {}
    for stem, recs in packs.items():
        for rec in recs:
            by_id[(stem, rec["id"])] = rec
    assert sheet["rank_rows"]
    for row in sheet["rank_rows"]:
        rec = by_id[(row["pack"], row["pair_id"])]
        expect = rec["hist"][-1] & 0x0F
        assert row["site_nib"] == expect
        coord = _hex_to_bytes(row["coord_hex"])
        assert (coord[-1] & 0x0F) == row["site_nib"]


def test_tsg_u04_occ(sheet):
    """Boundary mid-features use half-open windows; disagreed sides never grant."""
    meta_path = ENV / "data" / ("window" + "_meta.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    bands = [(w["lo"], w["hi"]) for w in meta["win" + "dows"]]
    pack_recs = _load_tlf(ENV / "packs" / "a2_blob_01.tlf")
    mid_by_id = {rec["id"]: rec["feats"][len(rec["feats"]) // 2] for rec in pack_recs}

    def expected_band(value):
        for lo, hi in bands:
            if lo <= value < hi:
                return lo, hi
        return bands[0]

    for row in sheet["rank_rows"]:
        if row["pack"] != "a2_blob_01" or row["pair_id"] not in mid_by_id:
            continue
        lo, hi = expected_band(mid_by_id[row["pair_id"]])
        assert (row["win_lo"], row["win_hi"]) == (lo, hi)
    by_pair = {}
    for row in sheet["rank_rows"]:
        if row["pack"] != "a2_blob_01":
            continue
        pid = row["pair_id"]
        if pid not in by_pair:
            by_pair[pid] = []
        by_pair[pid].append(row)
    for rows in by_pair.values():
        sides = {r["side"]: r for r in rows}
        if "a" in sides and "b" in sides:
            if sides["a"]["win_lo"] != sides["b"]["win_lo"]:
                assert sides["a"]["slot_ok"] == 0 and sides["b"]["slot_ok"] == 0


def test_tsg_u05_dup():
    """Chrono twice stays idempotent: no duplicate rank row identities."""
    data1 = _regen()
    _run_jar()
    data2 = json.loads(OUT.read_text(encoding="utf-8"))
    assert data1["rank_rows"] == data2["rank_rows"]
    seen = set()
    for row in data1["rank_rows"]:
        key = (row["pair_id"], row["side"])
        assert key not in seen
        seen.add(key)


def test_tsg_u06_ln(sheet):
    """Chrono open sequence freshness counters chain for c8 pack."""
    c8_ids = {r["pair_id"] for r in sheet["rank_rows"] if r["pack"] == "c8_ln_03"}
    surfs = [
        t
        for t in sheet["shift_surfaces"]
        if t["wave"] == "chrono" and t["pack"] == "c8_ln_03"
    ]
    assert len(surfs) >= 2
    first_block = [surfs[0]]
    for t in surfs[1:]:
        expected = first_block[-1]["freshness"] + 1
        if t["freshness"] != expected:
            break
        first_block.append(t)
    assert len(first_block) >= 2
    assert first_block[0]["freshness"] >= 1
    assert c8_ids


def test_tsg_u07_mix(sheet):
    """Merged shuffle and chrono lanes appear together with packed coords."""
    waves = {w["name"] for w in sheet["waves"]}
    run_waves = {r["wave"] for r in sheet["runs"]}
    assert "shuffle" in waves and "chrono" in waves
    assert "shuffle" in run_waves and "chrono" in run_waves
    assert sheet["rank_rows"], "merged sheet must materialize rank rows"
    assert sheet["shift_surfaces"], "merged sheet must materialize shift surfaces"
    for row in sheet["rank_rows"]:
        assert len(row["coord_hex"]) % 2 == 0
        _hex_to_bytes(row["coord_hex"])


def test_tsg_u08_hex(sheet):
    """Chrono-wave slot_ok follows high nibble bit of the first coord byte."""
    checked = 0
    for row in sheet["rank_rows"]:
        if row["pack"] != "c8_ln_03":
            continue
        sides = [
            r
            for r in sheet["rank_rows"]
            if r["pair_id"] == row["pair_id"]
        ]
        if len({s["win_lo"] for s in sides}) > 1:
            continue
        coord = _hex_to_bytes(row["coord_hex"])
        expect = (coord[0] >> 4) & 1
        assert row["slot_ok"] == expect
        checked += 1
    assert checked >= 1
