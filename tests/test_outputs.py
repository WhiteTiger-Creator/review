"""Domain verifier for saml-umt-route-holdout."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
OUT = APP / "output" / "sol_run.json"
SEAL = APP / "output" / "replay_seal.json"
SIDE = APP / "output" / "side"
BLOB = APP / "data" / "annex31" / "slot_blob.bin"
MANIFEST = APP / "data" / "annex31" / "manifest.json"
PIPE_SEED = 0x4D31A7
BLOB_MAGIC = 0xA31C0FFE
K_PRIME = 0x100000001B3
HEX_DIGITS = 16
DUTY_MIX = 0x631A31C0

EDGES = {
    (1, "a0"): "a1",
    (1, "a1"): "a2",
    (1, "a2"): "a0",
    (2, "b0"): "b1",
    (2, "b1"): "b2",
    (2, "b2"): "b0",
    (3, "c0"): "c1",
    (3, "c1"): "c2",
    (3, "c2"): "c0",
    (4, "d0"): "d1",
    (4, "d1"): "d2",
    (4, "d2"): "d3",
    (4, "d3"): "d0",
}

START = {1: "a0", 2: "b0", 3: "c0", 4: "d0"}


def _hex16(v: int) -> str:
    return f"{v & 0xFFFFFFFFFFFFFFFF:016x}"


def _bound_seed() -> int:
    return PIPE_SEED ^ (BLOB_MAGIC & 0xFFFFFF)


def _hold_walk_mix(epoch: int, pad: int) -> int:
    """Published hold walk latch: ((E + (pad * 3)) ^ (pad << 2)) & 0xff."""
    return ((epoch + (pad * 3)) ^ (pad << 2)) & 0xFF


def _hold_walk_sum_false_green(epoch: int, pad: int) -> int:
    return (epoch + pad) & 0xFF


def _hold_walk_product_false_green(epoch: int, pad: int) -> int:
    return (epoch * pad) & 0xFF


def _mix_label(h: int, lab: str) -> int:
    for c in lab:
        h ^= ord(c)
        h = (h * K_PRIME) & 0xFFFFFFFFFFFFFFFF
    return h


def _hop_digest(
    pad: int,
    seed: int | None = None,
    *,
    arm: int = 0,
    epoch: int | None = None,
) -> int:
    if seed is None:
        seed = _bound_seed()
    if arm != 0:
        if epoch is None:
            epoch = _epoch()
        seed = seed ^ _hold_walk_mix(epoch, pad)
    cur = START[pad]
    start = cur
    h = (seed ^ (pad * 0xC2B2AE3D)) & 0xFFFFFFFFFFFFFFFF
    h = _mix_label(h, cur)
    while True:
        cur = EDGES[(pad, cur)]
        h = _mix_label(h, cur)
        if cur == start:
            break
    return h


def _short_hop_digest(pad: int, seed: int | None = None) -> int:
    """Two-label short walk (starter false-green); must not match live hops."""
    if seed is None:
        seed = _bound_seed()
    cur = START[pad]
    h = (seed ^ (pad * 0xC2B2AE3D)) & 0xFFFFFFFFFFFFFFFF
    h = _mix_label(h, cur)
    cur = EDGES[(pad, cur)]
    return _mix_label(h, cur)


def _span(
    h: int,
    lo: int,
    hi: int,
    w: int,
    *,
    arm: int = 0,
    epoch: int = 0,
    pad: int = 0,
) -> int:
    width = (hi - lo) & 0xFFFFFFFF
    lo_term = ((lo & 0xFFFFFFFF) << 1) ^ (w & 0xFFFFFFFF)
    if arm != 0:
        hold_mix = (
            (epoch & 0xFF)
            ^ pad
            ^ ((pad & 0xFF) << 8)
            ^ ((epoch & 0xFF) << 16)
        )
        lo_term ^= hold_mix
    return (
        (width * 0x9E3779B9)
        ^ (h & 0xFFFFFFFF)
        ^ lo_term
    ) & 0xFFFFFFFFFFFFFFFF


def _rotl64(x: int, n: int) -> int:
    n &= 63
    x &= 0xFFFFFFFFFFFFFFFF
    return ((x << n) | (x >> (64 - n))) & 0xFFFFFFFFFFFFFFFF


def _hold_rotate(pad: int, epoch: int) -> int:
    return {1: 13, 2: 19, 3: 23, 4: 29}[pad] + (epoch % 3)


def _stamp_rotate(arm: str, pad: int, epoch: int) -> int:
    if arm != "hold":
        return 1
    base = {1: 3, 2: 5, 3: 7, 4: 11}[pad]
    return base + (epoch % 5)


def _pad_mix(pad: int, epoch: int) -> int:
    return (
        (pad * 0xA5A5)
        ^ (epoch & 0xFF)
        ^ (pad << 16)
        ^ ((epoch % 3) << 24)
        ^ (((epoch & 0xFF) << 8) | (pad & 0xFF))
    )


def _exact(h: int, pad: int, arm: int, lo: int, hi: int, w: int, epoch: int) -> int:
    # full unsigned 64-bit product; no 32-bit truncate before xor
    base = ((h & 0xFFFFFFFF) ^ (lo * w)) & 0xFFFFFFFFFFFF
    if arm != 0:
        return (
            _rotl64(base, _hold_rotate(pad, epoch)) ^ hi ^ _pad_mix(pad, epoch)
        ) & 0xFFFFFFFFFFFF
    return base


def _hold_mesh(rows: list[dict]) -> int:
    acc = 0
    for r in rows:
        if r["arm"] == "hold":
            acc ^= int(r["hop_key"], 16)
    return acc & 0xFFFFFFFFFFFFFFFF


def _fold_mesh(rows: list[dict]) -> int:
    acc = 0
    for r in sorted(rows, key=lambda x: x["row_id"]):
        if r["arm"] == "hold":
            acc ^= int(r["fold_tag"]) & 0xFFFFFFFFFFFFFFFF
    return acc & 0xFFFFFFFFFFFFFFFF


def _u16(buf: bytes, off: int) -> int:
    return int.from_bytes(buf[off : off + 2], "little")


def _u32(buf: bytes, off: int) -> int:
    return int.from_bytes(buf[off : off + 4], "little")


def _load_rows() -> list[dict]:
    raw = BLOB.read_bytes()
    magic = _u32(raw, 0)
    count = _u32(raw, 4)
    assert magic == BLOB_MAGIC
    off = 8
    rows: list[dict] = []
    for _ in range(count):
        id_len = _u16(raw, off)
        off += 2
        rid = raw[off : off + id_len].decode("utf-8")
        off += id_len
        pad = raw[off]
        arm = raw[off + 1]
        off += 2
        _slot_ix = _u32(raw, off)
        lo = _u32(raw, off + 4)
        hi = _u32(raw, off + 8)
        w = _u32(raw, off + 12)
        off += 16
        rows.append({"id": rid, "pad": pad, "arm": arm, "lo": lo, "hi": hi, "w": w})
    return rows


def _epoch() -> int:
    return int(json.loads(MANIFEST.read_text(encoding="utf-8"))["epoch"])


def _auth_stamp(rows: list[dict], pads: dict[str, int], epoch: int) -> str:
    acc = 0
    for r in sorted(rows, key=lambda x: x["row_id"]):
        hk = int(r["hop_key"], 16)
        rot = _stamp_rotate(r["arm"], pads[r["row_id"]], epoch)
        acc ^= _rotl64(hk, rot) ^ int(r["fold_tag"]) ^ int(r["span_u64"])
    acc ^= DUTY_MIX
    return _hex16(acc)


def _replay_seal(
    mesh_hex: str,
    stamp_hex: str,
    epoch: int,
    hold_mesh: int = 0,
    fold_mesh: int = 0,
) -> str:
    mesh = int(mesh_hex, 16)
    stamp = int(stamp_hex, 16)
    acc = (
        _rotl64(mesh, 5)
        ^ stamp
        ^ ((epoch & 0xFFFFFFFF) << 16)
        ^ DUTY_MIX
        ^ _rotl64(hold_mesh, 3 + (epoch % 5))
        ^ _rotl64(fold_mesh, 2 + (epoch % 7))
    )
    return _hex16(acc)


def _expected() -> dict:
    rows_in = _load_rows()
    pads = {r["id"]: r["pad"] for r in rows_in}
    epoch = _epoch()
    out_rows = []
    train_mesh = 0
    hold_mesh = 0
    for r in sorted(rows_in, key=lambda x: x["id"]):
        h = _hop_digest(r["pad"], arm=r["arm"], epoch=epoch)
        tag = _exact(h, r["pad"], r["arm"], r["lo"], r["hi"], r["w"], epoch)
        sp = _span(
            h, r["lo"], r["hi"], r["w"], arm=r["arm"], epoch=epoch, pad=r["pad"]
        )
        arm_bit = 0 if r["arm"] == 0 else 1
        join = h ^ tag ^ sp ^ arm_bit
        if r["arm"] != 0:
            join ^= (
                (((epoch & 0xFF) << 8) | (r["pad"] & 0xFF))
                ^ ((epoch % 3) << 16)
            )
        if r["arm"] == 0:
            train_mesh ^= h
        else:
            hold_mesh ^= h
        out_rows.append(
            {
                "row_id": r["id"],
                "hop_key": _hex16(h),
                "fold_tag": tag,
                "span_u64": sp,
                "join_hex": _hex16(join),
                "arm": "train" if r["arm"] == 0 else "hold",
                "pad": r["pad"],
            }
        )
    stamp = _auth_stamp(out_rows, pads, epoch)
    mesh = _rotl64(train_mesh ^ hold_mesh, _mesh_width(epoch)) & 0xFFFFFFFFFFFFFFFF
    mesh_hex = _hex16(mesh)
    hold = _hold_mesh(out_rows)
    fold = _fold_mesh(out_rows)
    return {
        "schema_version": 1,
        "mesh_digest": mesh_hex,
        "auth_stamp": stamp,
        "replay_seal": _replay_seal(mesh_hex, stamp, epoch, hold, fold),
        "epoch": epoch,
        "hold_mesh": hold,
        "fold_mesh": fold,
        "rows": out_rows,
    }


def _rebuild_and_run() -> None:
    subprocess.run(
        ["mvn", "-q", "-DskipTests", "package"],
        check=True,
        cwd="/app",
    )
    wrapper = APP / "bin" / "uxr"
    wrapper.write_text("#!/bin/bash\nexec java -jar /app/target/uxr-1.0.0.jar \"$@\"\n")
    wrapper.chmod(0o755)
    subprocess.run(["/app/bin/uxr"], check=True)


def _read_out() -> dict:
    return json.loads(OUT.read_text(encoding="utf-8"))


def _read_seal() -> dict:
    return json.loads(SEAL.read_text(encoding="utf-8"))


def _envelope_ok(arm: str, span: int) -> bool:
    if span >= (1 << 63):
        return False
    if arm == "hold":
        return (span % 97) < 89
    return True


def _write_hop_cache(seed: int, pairs: list[tuple[str, int]]) -> None:
    """Plant a side hop.cache with seed fingerprint and bogus hop lines."""
    chunks: list[str] = ["seed=", str(int(seed))]
    for key, val in pairs:
        chunks.extend(["\n", key, "=", str(int(val))])
    chunks.append("\n")
    (SIDE / "hop.cache").write_text("".join(chunks), encoding="utf-8")


def _write_duty_cache(pairs: list[tuple[str, int]]) -> None:
    chunks: list[str] = []
    for key, val in pairs:
        chunks.extend([key, "=", str(int(val)), "\n"])
    (SIDE / "duty.cache").write_text("".join(chunks), encoding="utf-8")


@pytest.fixture(scope="session", autouse=True)
def _ensure_artifact() -> None:
    if not OUT.exists() or not SEAL.exists():
        _rebuild_and_run()


def test_k01_run_ok() -> None:
    """Rebuild uxr and require schema_version=1 sol_run with envelope-safe spans."""
    _rebuild_and_run()
    assert OUT.exists()
    assert SEAL.exists()
    data = _read_out()
    assert data["schema_version"] == 1
    assert all(_envelope_ok(r["arm"], int(r["span_u64"])) for r in data["rows"])


def test_k02_schema_ok() -> None:
    """Check sol_run field presence and basic types from the published schema docs."""
    data = _read_out()
    assert isinstance(data["mesh_digest"], str)
    assert len(data["mesh_digest"]) == HEX_DIGITS
    assert isinstance(data["auth_stamp"], str)
    assert len(data["auth_stamp"]) == HEX_DIGITS
    assert isinstance(data["replay_seal"], str)
    assert len(data["replay_seal"]) == HEX_DIGITS
    assert isinstance(data["rows"], list)
    assert data["rows"]
    for row in data["rows"]:
        assert set(row) >= {
            "row_id",
            "hop_key",
            "fold_tag",
            "span_u64",
            "join_hex",
            "arm",
        }
        assert len(row["hop_key"]) == HEX_DIGITS
        assert len(row["join_hex"]) == HEX_DIGITS
        assert row["arm"] in ("train", "hold")
        assert isinstance(row["fold_tag"], int)
        assert isinstance(row["span_u64"], int)
    _assert_full_contract()


def test_k03_train_ok() -> None:
    """Training rows must keep hop_key and fold_tag matching the published fold walk."""
    exp = {r["row_id"]: r for r in _expected()["rows"] if r["arm"] == "train"}
    got = {r["row_id"]: r for r in _read_out()["rows"] if r["arm"] == "train"}
    assert set(got) == set(exp)
    for rid, er in exp.items():
        assert got[rid]["fold_tag"] == er["fold_tag"]
        assert got[rid]["hop_key"] == er["hop_key"]
        assert got[rid]["span_u64"] == er["span_u64"]
        assert got[rid]["join_hex"] == er["join_hex"]
    assert _read_out()["mesh_digest"] == _expected()["mesh_digest"]
    assert _read_out()["auth_stamp"] == _expected()["auth_stamp"]


def test_k04_hold_ok() -> None:
    """Hold rows must use pad-dependent exact fold tags and stay inside the hold envelope."""
    exp = {r["row_id"]: r for r in _expected()["rows"] if r["arm"] == "hold"}
    got = {r["row_id"]: r for r in _read_out()["rows"] if r["arm"] == "hold"}
    assert set(got) == set(exp)
    for rid, er in exp.items():
        assert got[rid]["fold_tag"] == er["fold_tag"]
        assert got[rid]["hop_key"] == er["hop_key"]
        # Short-walk false greens must not satisfy the live hold hop.
        assert got[rid]["hop_key"] != _hex16(_short_hop_digest(er["pad"]))
        assert _envelope_ok("hold", got[rid]["span_u64"])


def test_k05_span_ok() -> None:
    """span_u64 must match published span recomputation and envelope clauses."""
    exp = {r["row_id"]: r for r in _expected()["rows"]}
    for row in _read_out()["rows"]:
        er = exp[row["row_id"]]
        assert row["span_u64"] == er["span_u64"]
        assert _envelope_ok(row["arm"], row["span_u64"])


def test_k06_mesh_ok() -> None:
    """hop_key values and mesh_digest must match out_fields mesh composition."""
    exp = _expected()
    got = _read_out()
    assert got["mesh_digest"] == exp["mesh_digest"]
    epoch = _epoch()
    train = 0
    hold = 0
    for row in sorted(got["rows"], key=lambda r: r["row_id"]):
        hk = int(row["hop_key"], 16)
        if row["arm"] == "hold":
            hold ^= hk
        else:
            train ^= hk
    composed = _rotl64(train ^ hold, _mesh_width(epoch)) & 0xFFFFFFFFFFFFFFFF
    assert got["mesh_digest"] == _hex16(composed)
    # Prior false-green rotated train alone then xored hold; bare E%3 width also wrong.
    old_style = (_rotl64(train, _mesh_width(epoch)) ^ hold) & 0xFFFFFFFFFFFFFFFF
    bare_mod = _rotl64(train ^ hold, epoch % 3) & 0xFFFFFFFFFFFFFFFF
    if hold != 0 and train != 0:
        assert got["mesh_digest"] != _hex16(old_style) or old_style == composed
        if bare_mod != composed:
            assert got["mesh_digest"] != _hex16(bare_mod)
        assert got["mesh_digest"] != _hex16(train ^ hold) or (train ^ hold) == composed
    for row, er in zip(
        sorted(got["rows"], key=lambda r: r["row_id"]),
        sorted(exp["rows"], key=lambda r: r["row_id"]),
        strict=True,
    ):
        assert row["hop_key"] == er["hop_key"]
        short_seed = _bound_seed()
        if er["arm"] == "hold":
            short_seed ^= _hold_walk_mix(epoch, er["pad"])
        assert row["hop_key"] != _hex16(_short_hop_digest(er["pad"], short_seed))


def test_k07_rewrite() -> None:
    """Overwriting sol_run then rerunning uxr must regenerate a passing artifact."""
    OUT.write_text(
        '{"schema_version":0,"rows":[],"mesh_digest":"'
        + ("0" * HEX_DIGITS)
        + '","auth_stamp":"'
        + ("0" * HEX_DIGITS)
        + '","replay_seal":"'
        + ("0" * HEX_DIGITS)
        + '"}\n'
    )
    _rebuild_and_run()
    data = _read_out()
    assert data["schema_version"] == 1
    assert data["rows"]
    exp = _expected()
    assert data["mesh_digest"] == exp["mesh_digest"]
    assert data["auth_stamp"] == exp["auth_stamp"]
    assert data["replay_seal"] == exp["replay_seal"]


def test_k08_repeat() -> None:
    """Two consecutive identical uxr runs must bitwise-agree on sol_run."""
    _rebuild_and_run()
    a = OUT.read_bytes()
    sa = SEAL.read_bytes()
    _rebuild_and_run()
    b = OUT.read_bytes()
    sb = SEAL.read_bytes()
    assert a == b
    assert sa == sb
    _assert_full_contract()
    _assert_rejects_near_misses()


def test_k13_join_ok() -> None:
    """join_hex must match out_fields, including the hold epoch/pad mix."""
    epoch = _epoch()
    pads = {r["id"]: r["pad"] for r in _load_rows()}
    for row in _read_out()["rows"]:
        hk = int(row["hop_key"], 16)
        arm_bit = 0 if row["arm"] == "train" else 1
        join = int(row["join_hex"], 16)
        expect = (hk ^ row["fold_tag"] ^ row["span_u64"] ^ arm_bit) & 0xFFFFFFFFFFFFFFFF
        if row["arm"] == "hold":
            expect ^= _hold_join_mix(epoch, pads[row["row_id"]])
        assert join == expect
        if row["arm"] == "hold":
            bare = (hk ^ row["fold_tag"] ^ row["span_u64"] ^ arm_bit) & 0xFFFFFFFFFFFFFFFF
            pad = pads[row["row_id"]]
            assert join != bare
            if _hold_join_mix(epoch, pad) != (epoch & 0xFF):
                assert join != (bare ^ (epoch & 0xFF))
            # Pad nibble without ((E mod 3) << 16) collapses to live when E%3==0.
            shallow_join = ((epoch & 0xFF) << 8) | (pad & 0xFF)
            if _hold_join_mix(epoch, pad) != shallow_join:
                assert join != (bare ^ shallow_join)


def test_k14_stamp_ok() -> None:
    """auth_stamp must match the pad-dependent epoch-latched duty mix."""
    exp = _expected()
    got = _read_out()
    assert got["auth_stamp"] == exp["auth_stamp"]


def test_k15_cache_poison() -> None:
    """Stale side hop.cache must not freeze graded hops after regeneration."""
    _rebuild_and_run()
    (SIDE / "hop.cache").write_text("seed=0\nx=0\n", encoding="utf-8")
    _rebuild_and_run()
    exp = _expected()
    got = _read_out()
    assert got["mesh_digest"] == exp["mesh_digest"]
    assert got["auth_stamp"] == exp["auth_stamp"]
    assert got["replay_seal"] == exp["replay_seal"]
    for row, er in zip(
        sorted(got["rows"], key=lambda r: r["row_id"]),
        sorted(exp["rows"], key=lambda r: r["row_id"]),
        strict=True,
    ):
        assert row["hop_key"] == er["hop_key"]


def test_k16_seal_ok() -> None:
    """replay_seal in sol_run and seal_hex in replay_seal.json must match duty mix."""
    exp = _expected()
    got = _read_out()
    seal = _read_seal()
    assert got["replay_seal"] == exp["replay_seal"]
    assert seal["schema_version"] == 1
    assert seal["epoch"] == exp["epoch"]
    assert seal["seal_hex"] == exp["replay_seal"]


def test_k17_pad3_hold() -> None:
    """Pad-3 hold claims must use R=23 fold rotates and epoch-latched stamp rotates."""
    exp_rows = {
        r["row_id"]: r for r in _expected()["rows"] if r["pad"] == 3 and r["arm"] == "hold"
    }
    assert exp_rows, "fixture must include pad-3 hold rows"
    got = {r["row_id"]: r for r in _read_out()["rows"]}
    for rid, er in exp_rows.items():
        assert got[rid]["fold_tag"] == er["fold_tag"]
        assert got[rid]["hop_key"] == er["hop_key"]
    assert _read_out()["auth_stamp"] == _expected()["auth_stamp"]


def test_k18_pad_family() -> None:
    """Every published pad family must appear with matching hop_key digests."""
    pads = {r["pad"] for r in _load_rows()}
    assert pads == {1, 2, 3, 4}
    exp = {r["row_id"]: r for r in _expected()["rows"]}
    for row in _read_out()["rows"]:
        assert row["hop_key"] == exp[row["row_id"]]["hop_key"]
        assert row["fold_tag"] == exp[row["row_id"]]["fold_tag"]
        assert row["span_u64"] == exp[row["row_id"]]["span_u64"]
    _assert_rejects_near_misses()


def test_k21_pad4_cycle() -> None:
    """Pad-4 claims require the longer d0-d1-d2-d3-d0 walk, not a hardcoded three-step walk."""
    exp_rows = {r["row_id"]: r for r in _expected()["rows"] if r["pad"] == 4}
    assert len(exp_rows) >= 2
    got = {r["row_id"]: r for r in _read_out()["rows"]}
    epoch = _epoch()
    for rid, er in exp_rows.items():
        assert got[rid]["hop_key"] == er["hop_key"]
        assert got[rid]["fold_tag"] == er["fold_tag"]
        walk_seed = _bound_seed()
        if er["arm"] == "hold":
            walk_seed ^= _hold_walk_mix(epoch, 4)
        assert got[rid]["hop_key"] != _hex16(_short_hop_digest(4, walk_seed))
        assert got[rid]["hop_key"] != _hex16(_short_hop_digest(4, _bound_seed()))
        assert got[rid]["hop_key"] != _hex16(
            _short_hop_digest(4, _bound_seed() ^ (epoch & 0xFF))
        )


def test_k22_fold_width() -> None:
    """Overflow lo times w rows must use full 64-bit product before the 48-bit base mask."""
    wide = [r for r in _load_rows() if (r["lo"] * r["w"]) > 0xFFFFFFFF]
    assert wide, "fixture must include overflow fold rows"
    exp = {r["row_id"]: r for r in _expected()["rows"]}
    got = {r["row_id"]: r for r in _read_out()["rows"]}
    for r in wide:
        assert got[r["id"]]["fold_tag"] == exp[r["id"]]["fold_tag"]


def test_k23_seed_fingerprint() -> None:
    """A hop.cache with a mismatched seed fingerprint must not freeze graded hops."""
    _rebuild_and_run()
    wrong = _bound_seed() ^ 0xFFFFFF
    _write_hop_cache(wrong, [("t01", 1), ("h01", 2)])
    (SIDE / "fold.soft").write_text("1", encoding="utf-8")
    (SIDE / "span.soft").write_text("1", encoding="utf-8")
    _rebuild_and_run()
    _assert_full_contract()


def test_k24_epoch_latch() -> None:
    """Hold stamp rotates must latch pad base widths to annex epoch mod 5."""
    epoch = _epoch()
    assert _stamp_rotate("hold", 1, epoch) == 3 + (epoch % 5)
    assert _stamp_rotate("hold", 4, epoch) == 11 + (epoch % 5)
    assert _read_out()["auth_stamp"] == _expected()["auth_stamp"]
    assert _read_out()["replay_seal"] == _expected()["replay_seal"]


def test_k09_cache_live_seed() -> None:
    """hop.cache with a matching seed fingerprint but wrong hops must not freeze mesh."""
    _rebuild_and_run()
    seed = _bound_seed()
    # Plausible cache: correct seed line, bogus hop payloads.
    _write_hop_cache(
        seed,
        [("t01", 1), ("h01", 2), ("h02", 3), ("h03", 4), ("h04", 5)],
    )
    _rebuild_and_run()
    exp = _expected()
    got = _read_out()
    assert got["mesh_digest"] == exp["mesh_digest"]
    for row, er in zip(
        sorted(got["rows"], key=lambda r: r["row_id"]),
        sorted(exp["rows"], key=lambda r: r["row_id"]),
        strict=True,
    ):
        assert row["hop_key"] == er["hop_key"]
        assert row["fold_tag"] == er["fold_tag"]


def test_k10_cache_hold_regen() -> None:
    """After a poisoned hop.cache, hold fold tags and envelope spans must still match."""
    _rebuild_and_run()
    (SIDE / "hop.cache").write_text("seed=0\nshort=1\n", encoding="utf-8")
    _rebuild_and_run()
    exp = {r["row_id"]: r for r in _expected()["rows"] if r["arm"] == "hold"}
    got = {r["row_id"]: r for r in _read_out()["rows"] if r["arm"] == "hold"}
    assert exp
    for rid, er in exp.items():
        assert got[rid]["fold_tag"] == er["fold_tag"]
        assert got[rid]["span_u64"] == er["span_u64"]
        assert _envelope_ok("hold", got[rid]["span_u64"])


def test_k11_input_epoch_only() -> None:
    """Changing only the annex manifest epoch (input mutation) must retarget stamp and seal."""
    manifest = MANIFEST
    original = manifest.read_text(encoding="utf-8")
    try:
        _rebuild_and_run()
        base_epoch = _epoch()
        new_epoch = base_epoch + 3
        manifest.write_text(
            original.replace(f'"epoch": {base_epoch}', f'"epoch": {new_epoch}'),
            encoding="utf-8",
        )
        old = _read_out()
        _rebuild_and_run()
        exp = _expected()
        got = _read_out()
        assert exp["epoch"] == new_epoch
        assert got["auth_stamp"] == exp["auth_stamp"]
        assert got["replay_seal"] == exp["replay_seal"]
        assert _read_seal()["epoch"] == new_epoch
        assert _read_seal()["seal_hex"] == exp["replay_seal"]
        if base_epoch % 5 != new_epoch % 5:
            assert got["auth_stamp"] != old["auth_stamp"]
            assert got["replay_seal"] != old["replay_seal"]
    finally:
        manifest.write_text(original, encoding="utf-8")
        _rebuild_and_run()


def test_k12_stamp_after_side_disturbance() -> None:
    """Poisoned hop.cache plus a stale seal.hint must still yield a live auth_stamp."""
    _rebuild_and_run()
    (SIDE / "hop.cache").write_text("seed=99\nz=0\n", encoding="utf-8")
    jrn = SIDE / "jrn"
    jrn.mkdir(parents=True, exist_ok=True)
    (jrn / "seal.hint").write_text("42", encoding="utf-8")
    _rebuild_and_run()
    exp = _expected()
    got = _read_out()
    assert got["auth_stamp"] == exp["auth_stamp"]
    assert got["replay_seal"] == exp["replay_seal"]
    assert _read_seal()["seal_hex"] == exp["replay_seal"]


def test_k19_cache_then_epoch() -> None:
    """Poison cache, then advance manifest epoch; hops and stamp must both follow live authority."""
    manifest = MANIFEST
    original = manifest.read_text(encoding="utf-8")
    try:
        _rebuild_and_run()
        _write_hop_cache(_bound_seed(), [("t01", 7), ("h01", 8)])
        base_epoch = _epoch()
        new_epoch = base_epoch + 2
        manifest.write_text(
            original.replace(f'"epoch": {base_epoch}', f'"epoch": {new_epoch}'),
            encoding="utf-8",
        )
        _rebuild_and_run()
        exp = _expected()
        got = _read_out()
        assert got["mesh_digest"] == exp["mesh_digest"]
        assert got["auth_stamp"] == exp["auth_stamp"]
        assert got["replay_seal"] == exp["replay_seal"]
        for row, er in zip(
            sorted(got["rows"], key=lambda r: r["row_id"]),
            sorted(exp["rows"], key=lambda r: r["row_id"]),
            strict=True,
        ):
            assert row["hop_key"] == er["hop_key"]
    finally:
        manifest.write_text(original, encoding="utf-8")
        _rebuild_and_run()


def test_k20_seal_hint_plausible() -> None:
    """A seal.hint carrying the previous run's seal must not freeze the next regeneration."""
    _rebuild_and_run()
    prev_seal = int(_read_out()["replay_seal"], 16)
    jrn = SIDE / "jrn"
    jrn.mkdir(parents=True, exist_ok=True)
    (jrn / "seal.hint").write_text(str(prev_seal ^ 0xFFFF), encoding="utf-8")
    # Also bump epoch so a frozen hint would visibly diverge from live seal.
    manifest = MANIFEST
    original = manifest.read_text(encoding="utf-8")
    try:
        base_epoch = _epoch()
        new_epoch = base_epoch + 1
        manifest.write_text(
            original.replace(f'"epoch": {base_epoch}', f'"epoch": {new_epoch}'),
            encoding="utf-8",
        )
        _rebuild_and_run()
        exp = _expected()
        got = _read_out()
        assert got["replay_seal"] == exp["replay_seal"]
        assert _read_seal()["seal_hex"] == exp["replay_seal"]
        assert got["replay_seal"] != _hex16(prev_seal)
    finally:
        manifest.write_text(original, encoding="utf-8")
        _rebuild_and_run()


def test_k25_epoch_snap_plausible() -> None:
    """An epoch.snap equal to a prior manifest epoch must lose to a newer annex epoch."""
    manifest = MANIFEST
    original = manifest.read_text(encoding="utf-8")
    try:
        _rebuild_and_run()
        base_epoch = _epoch()
        jrn = SIDE / "jrn"
        jrn.mkdir(parents=True, exist_ok=True)
        (jrn / "epoch.snap").write_text(str(base_epoch), encoding="utf-8")
        new_epoch = base_epoch + 4
        manifest.write_text(
            original.replace(f'"epoch": {base_epoch}', f'"epoch": {new_epoch}'),
            encoding="utf-8",
        )
        _rebuild_and_run()
        exp = _expected()
        got = _read_out()
        assert exp["epoch"] == new_epoch
        assert got["auth_stamp"] == exp["auth_stamp"]
        assert got["replay_seal"] == exp["replay_seal"]
        assert _read_seal()["epoch"] == new_epoch
    finally:
        manifest.write_text(original, encoding="utf-8")
        if (SIDE / "jrn" / "epoch.snap").exists():
            (SIDE / "jrn" / "epoch.snap").unlink()
        _rebuild_and_run()


def test_k26_jrn_seal_hint() -> None:
    """Stale side/jrn/seal.hint must not freeze graded replay_seal after regeneration."""
    _rebuild_and_run()
    jrn = SIDE / "jrn"
    jrn.mkdir(parents=True, exist_ok=True)
    (jrn / "seal.hint").write_text("1", encoding="utf-8")
    _rebuild_and_run()
    exp = _expected()
    got = _read_out()
    seal = _read_seal()
    assert got["replay_seal"] == exp["replay_seal"]
    assert seal["seal_hex"] == exp["replay_seal"]


def test_k27_epoch_snap() -> None:
    """Leftover jrn/epoch.snap must not replace the annex manifest epoch for stamp latch."""
    _rebuild_and_run()
    jrn = SIDE / "jrn"
    jrn.mkdir(parents=True, exist_ok=True)
    (jrn / "epoch.snap").write_text(str(_epoch() + 17), encoding="utf-8")
    _rebuild_and_run()
    exp = _expected()
    got = _read_out()
    assert got["auth_stamp"] == exp["auth_stamp"]
    assert got["replay_seal"] == exp["replay_seal"]
    assert _read_seal()["epoch"] == exp["epoch"]


def test_k28_epoch_mutate() -> None:
    """After manifest epoch changes, stamp and seal must follow the new epoch on regeneration."""
    manifest = MANIFEST
    original = manifest.read_text(encoding="utf-8")
    try:
        _rebuild_and_run()
        base_epoch = _epoch()
        new_epoch = base_epoch + 1
        manifest.write_text(
            original.replace(f'"epoch": {base_epoch}', f'"epoch": {new_epoch}'),
            encoding="utf-8",
        )
        jrn = SIDE / "jrn"
        jrn.mkdir(parents=True, exist_ok=True)
        (jrn / "epoch.snap").write_text(str(base_epoch), encoding="utf-8")
        old_seal = _read_out()["replay_seal"]
        _rebuild_and_run()
        exp = _expected()
        got = _read_out()
        assert exp["epoch"] == new_epoch
        assert got["auth_stamp"] == exp["auth_stamp"]
        assert got["replay_seal"] == exp["replay_seal"]
        assert got["replay_seal"] != old_seal or base_epoch % 5 == new_epoch % 5
        assert _read_seal()["epoch"] == new_epoch
        assert _read_seal()["seal_hex"] == exp["replay_seal"]
    finally:
        manifest.write_text(original, encoding="utf-8")
        _rebuild_and_run()


def test_k29_side_wipe() -> None:
    """Wiping /app/output/side entirely must still regenerate a contract-correct sol_run."""
    import shutil

    _rebuild_and_run()
    if SIDE.exists():
        shutil.rmtree(SIDE)
    _rebuild_and_run()
    _assert_full_contract()
    assert SIDE.exists()


def test_k30_dual_poison() -> None:
    """Poisoned hop.cache plus seal.hint and epoch.snap must all yield to live regeneration."""
    _rebuild_and_run()
    _write_hop_cache(0, [("t01", 1)])
    jrn = SIDE / "jrn"
    jrn.mkdir(parents=True, exist_ok=True)
    (jrn / "seal.hint").write_text("99", encoding="utf-8")
    (jrn / "epoch.snap").write_text("1", encoding="utf-8")
    _rebuild_and_run()
    exp = _expected()
    got = _read_out()
    assert got["mesh_digest"] == exp["mesh_digest"]
    assert got["auth_stamp"] == exp["auth_stamp"]
    assert got["replay_seal"] == exp["replay_seal"]
    for row, er in zip(
        sorted(got["rows"], key=lambda r: r["row_id"]),
        sorted(exp["rows"], key=lambda r: r["row_id"]),
        strict=True,
    ):
        assert row["hop_key"] == er["hop_key"]
        assert row["fold_tag"] == er["fold_tag"]
        assert row["span_u64"] == er["span_u64"]
    _assert_rejects_near_misses(got)


def test_k31_triple_agree() -> None:
    """Three consecutive identical uxr runs must bitwise-agree on sol_run and replay_seal."""
    _rebuild_and_run()
    a_out = OUT.read_bytes()
    a_seal = SEAL.read_bytes()
    _rebuild_and_run()
    b_out = OUT.read_bytes()
    b_seal = SEAL.read_bytes()
    _rebuild_and_run()
    c_out = OUT.read_bytes()
    c_seal = SEAL.read_bytes()
    assert a_out == b_out == c_out
    assert a_seal == b_seal == c_seal
    _assert_full_contract()
    _assert_rejects_near_misses()


def test_k32_stamp_seal_identity() -> None:
    """replay_seal must equal duty_home over mesh, stamp, epoch, hold_mesh, and fold_mesh."""
    _rebuild_and_run()
    (SIDE / "stamp.soft").write_text("3", encoding="utf-8")
    _write_duty_cache([("hold:2", 1), ("train:3", 8)])
    (SIDE / "jrn").mkdir(parents=True, exist_ok=True)
    (SIDE / "jrn" / "seal.hint").write_text("99", encoding="utf-8")
    _rebuild_and_run()
    got = _read_out()
    seal = _read_seal()
    derived = _replay_seal(
        got["mesh_digest"],
        got["auth_stamp"],
        seal["epoch"],
        _hold_mesh(got["rows"]),
        _fold_mesh(got["rows"]),
    )
    assert got["replay_seal"] == derived
    assert seal["seal_hex"] == derived
    without = _replay_seal(got["mesh_digest"], got["auth_stamp"], seal["epoch"], 0, 0)
    assert without != got["replay_seal"] or (
        _hold_mesh(got["rows"]) == 0 and _fold_mesh(got["rows"]) == 0
    )
    _assert_full_contract()


def test_k33_hold_all_pads() -> None:
    """Every pad family hold row must match published fold tags and stay envelope-safe."""
    exp = {r["row_id"]: r for r in _expected()["rows"] if r["arm"] == "hold"}
    got = {r["row_id"]: r for r in _read_out()["rows"] if r["arm"] == "hold"}
    pads = {er["pad"] for er in exp.values()}
    assert pads == {1, 2, 3, 4}
    for rid, er in exp.items():
        assert got[rid]["fold_tag"] == er["fold_tag"]
        assert got[rid]["hop_key"] == er["hop_key"]
        assert got[rid]["span_u64"] == er["span_u64"]
        assert _envelope_ok("hold", got[rid]["span_u64"])


def test_k34_train_join_mesh() -> None:
    """Training rows must keep join_hex and contribute correctly to mesh_digest."""
    exp = _expected()
    got = _read_out()
    assert got["mesh_digest"] == exp["mesh_digest"]
    for row in got["rows"]:
        if row["arm"] != "train":
            continue
        hk = int(row["hop_key"], 16)
        join = int(row["join_hex"], 16)
        assert join == (hk ^ row["fold_tag"] ^ row["span_u64"]) & 0xFFFFFFFFFFFFFFFF
        assert row["hop_key"] == next(
            r["hop_key"] for r in exp["rows"] if r["row_id"] == row["row_id"]
        )
    assert got["auth_stamp"] == exp["auth_stamp"]
    assert got["replay_seal"] == exp["replay_seal"]
    _assert_rejects_near_misses(got)


def test_k35_manifest_epoch_in_seal_file() -> None:
    """replay_seal.json epoch must equal the annex manifest epoch after regeneration."""
    _rebuild_and_run()
    assert _read_seal()["epoch"] == _epoch()
    assert _read_seal()["seal_hex"] == _read_out()["replay_seal"]
    (SIDE / "jrn").mkdir(parents=True, exist_ok=True)
    (SIDE / "jrn" / "epoch.snap").write_text(str(_epoch() + 99), encoding="utf-8")
    (SIDE / "jrn" / "seal.hint").write_text("55", encoding="utf-8")
    _rebuild_and_run()
    assert _read_seal()["epoch"] == _epoch()
    assert _read_seal()["seal_hex"] == _expected()["replay_seal"]
    _assert_full_contract()


def test_k36_journal_mesh_snap() -> None:
    """Leftover mesh.snap plus seal.hint must not override live mesh or seal identities."""
    _rebuild_and_run()
    jrn = SIDE / "jrn"
    jrn.mkdir(parents=True, exist_ok=True)
    (jrn / "mesh.snap").write_text("999", encoding="utf-8")
    (jrn / "seal.hint").write_text("1", encoding="utf-8")
    (jrn / "seal.note").write_text("2", encoding="utf-8")
    _rebuild_and_run()
    exp = _expected()
    got = _read_out()
    assert got["mesh_digest"] == exp["mesh_digest"]
    assert got["replay_seal"] == exp["replay_seal"]
    assert _read_seal()["seal_hex"] == exp["replay_seal"]


def test_k37_epoch_journal_and_cache() -> None:
    """Stale epoch.snap with a poisoned hop.cache must still follow the annex epoch."""
    _rebuild_and_run()
    (SIDE / "hop.cache").write_text("seed=0\nbad=1\n", encoding="utf-8")
    jrn = SIDE / "jrn"
    jrn.mkdir(parents=True, exist_ok=True)
    (jrn / "epoch.snap").write_text(str(_epoch() + 11), encoding="utf-8")
    _rebuild_and_run()
    exp = _expected()
    got = _read_out()
    assert got["mesh_digest"] == exp["mesh_digest"]
    assert got["auth_stamp"] == exp["auth_stamp"]
    assert got["replay_seal"] == exp["replay_seal"]
    assert _read_seal()["epoch"] == exp["epoch"]


def test_k38_seed_mask() -> None:
    """Seed binding must xor the low 24 bits of annex magic, not a narrower mask."""
    exp = _expected()
    got = _read_out()
    assert got["mesh_digest"] == exp["mesh_digest"]
    # Wrong 16-bit mask would shift every hop_key.
    assert all(
        r["hop_key"] == e["hop_key"]
        for r, e in zip(
            sorted(got["rows"], key=lambda x: x["row_id"]),
            sorted(exp["rows"], key=lambda x: x["row_id"]),
            strict=True,
        )
    )
    _assert_full_contract()
    _assert_rejects_near_misses(got)


def test_k39_duty_mod5() -> None:
    """Hold stamp rotates must use epoch mod 5, not a neighboring modulus."""
    epoch = _epoch()
    assert _stamp_rotate("hold", 2, epoch) == 5 + (epoch % 5)
    assert _stamp_rotate("hold", 3, epoch) == 7 + (epoch % 5)
    got = _read_out()
    exp = _expected()
    assert got["auth_stamp"] == exp["auth_stamp"]
    wrong_mod4 = {
        1: 3 + (epoch % 4),
        2: 5 + (epoch % 4),
        3: 7 + (epoch % 4),
        4: 11 + (epoch % 4),
    }
    # Sanity: published latch differs from mod-4 for this fixture epoch.
    assert any(wrong_mod4[p] != _stamp_rotate("hold", p, epoch) for p in (1, 2, 3, 4)) or (
        epoch % 5 == epoch % 4
    )


def test_k40_regen_after_partial_rows() -> None:
    """Truncating sol_run rows then regenerating must restore the full annex row set."""
    _rebuild_and_run()
    OUT.write_text(
        '{"schema_version":1,"mesh_digest":"'
        + ("f" * 16)
        + '","auth_stamp":"'
        + ("e" * 16)
        + '","replay_seal":"'
        + ("d" * 16)
        + '","rows":[{"row_id":"t01","hop_key":"'
        + ("0" * 16)
        + '","fold_tag":0,"span_u64":0,"join_hex":"'
        + ("0" * 16)
        + '","arm":"train"}]}\n',
        encoding="utf-8",
    )
    _rebuild_and_run()
    exp = _expected()
    got = _read_out()
    assert len(got["rows"]) == len(exp["rows"])
    assert got["mesh_digest"] == exp["mesh_digest"]
    assert got["auth_stamp"] == exp["auth_stamp"]
    assert got["replay_seal"] == exp["replay_seal"]


def _pad_mix_missing_mod3_shift(pad: int, epoch: int) -> int:
    """Near-miss padMix that drops ((E mod 3) << 24)."""
    return (
        (pad * 0xA5A5)
        ^ (epoch & 0xFF)
        ^ (pad << 16)
        ^ (((epoch & 0xFF) << 8) | (pad & 0xFF))
    )


def _pad_mix_missing_nibble(pad: int, epoch: int) -> int:
    """Near-miss padMix that drops the join-nibble term."""
    return (
        (pad * 0xA5A5)
        ^ (epoch & 0xFF)
        ^ (pad << 16)
        ^ ((epoch % 3) << 24)
    )


def _span_missing_pad_shift(h: int, lo: int, hi: int, w: int, epoch: int, pad: int) -> int:
    """Near-miss hold span without ((E & 0xff) << 16)."""
    width = (hi - lo) & 0xFFFFFFFF
    lo_term = (((lo & 0xFFFFFFFF) << 1) ^ (w & 0xFFFFFFFF)) ^ (
        (epoch & 0xFF) ^ pad ^ ((pad & 0xFF) << 8)
    )
    return ((width * 0x9E3779B9) ^ (h & 0xFFFFFFFF) ^ lo_term) & 0xFFFFFFFFFFFFFFFF


def _fold_missing_mod3_shift(h: int, pad: int, lo: int, hi: int, w: int, epoch: int) -> int:
    base = ((h & 0xFFFFFFFF) ^ (lo * w)) & 0xFFFFFFFFFFFF
    return (
        _rotl64(base, _hold_rotate(pad, epoch)) ^ hi ^ _pad_mix_missing_mod3_shift(pad, epoch)
    ) & 0xFFFFFFFFFFFF


def _hold_join_mix(epoch: int, pad: int) -> int:
    return (((epoch & 0xFF) << 8) | (pad & 0xFF)) ^ ((epoch % 3) << 16)


def _mesh_width(epoch: int) -> int:
    return 1 + (epoch % 3)


def _assert_rejects_near_misses(got: dict | None = None, epoch: int | None = None) -> None:
    """Reject common near-miss formulas that still look locally deterministic."""
    if got is None:
        got = _read_out()
    if epoch is None:
        epoch = _epoch()
    rows_in = {r["id"]: r for r in _load_rows()}
    seed = _bound_seed()
    train = 0
    hold = 0
    for row in sorted(got["rows"], key=lambda r: r["row_id"]):
        meta = rows_in[row["row_id"]]
        hk = int(row["hop_key"], 16)
        if row["arm"] == "hold":
            hold ^= hk
            product = _hop_digest(
                meta["pad"],
                seed ^ _hold_walk_product_false_green(epoch, meta["pad"]),
                arm=0,
                epoch=epoch,
            )
            flat = _hop_digest(meta["pad"], seed ^ (epoch & 0xFF), arm=0, epoch=epoch)
            if _hold_walk_mix(epoch, meta["pad"]) != _hold_walk_product_false_green(
                epoch, meta["pad"]
            ):
                assert hk != product
            if _hold_walk_mix(epoch, meta["pad"]) != (epoch & 0xFF):
                assert hk != flat
            if _hold_walk_mix(epoch, meta["pad"]) != _hold_walk_sum_false_green(
                epoch, meta["pad"]
            ):
                assert hk != _hop_digest(
                    meta["pad"],
                    seed ^ _hold_walk_sum_false_green(epoch, meta["pad"]),
                    arm=0,
                    epoch=epoch,
                )
            if (epoch % 3) != 0:
                assert row["fold_tag"] != _fold_missing_mod3_shift(
                    hk, meta["pad"], meta["lo"], meta["hi"], meta["w"], epoch
                )
            if _pad_mix(meta["pad"], epoch) != _pad_mix_missing_nibble(meta["pad"], epoch):
                base = ((hk & 0xFFFFFFFF) ^ (meta["lo"] * meta["w"])) & 0xFFFFFFFFFFFF
                miss_n = (
                    _rotl64(base, _hold_rotate(meta["pad"], epoch))
                    ^ meta["hi"]
                    ^ _pad_mix_missing_nibble(meta["pad"], epoch)
                ) & 0xFFFFFFFFFFFF
                assert row["fold_tag"] != miss_n
            assert row["span_u64"] != _span_missing_pad_shift(
                hk, meta["lo"], meta["hi"], meta["w"], epoch, meta["pad"]
            )
            bare_join = (hk ^ row["fold_tag"] ^ row["span_u64"] ^ 1) & 0xFFFFFFFFFFFFFFFF
            join_live = bare_join ^ _hold_join_mix(epoch, meta["pad"])
            assert int(row["join_hex"], 16) == join_live
            if _hold_join_mix(epoch, meta["pad"]) != (epoch & 0xFF):
                assert int(row["join_hex"], 16) != (bare_join ^ (epoch & 0xFF))
            # Pad nibble without ((E mod 3) << 16) collapses to live when E%3==0.
            shallow_join = ((epoch & 0xFF) << 8) | (meta["pad"] & 0xFF)
            if _hold_join_mix(epoch, meta["pad"]) != shallow_join:
                assert int(row["join_hex"], 16) != (bare_join ^ shallow_join)
        else:
            train ^= hk
    composed = _rotl64(train ^ hold, _mesh_width(epoch)) & 0xFFFFFFFFFFFFFFFF
    assert got["mesh_digest"] == _hex16(composed)
    old_mesh = (_rotl64(train, _mesh_width(epoch)) ^ hold) & 0xFFFFFFFFFFFFFFFF
    bare_mod = _rotl64(train ^ hold, epoch % 3) & 0xFFFFFFFFFFFFFFFF
    if hold != 0 and train != 0:
        assert got["mesh_digest"] != _hex16(old_mesh) or old_mesh == composed
        if bare_mod != composed:
            assert got["mesh_digest"] != _hex16(bare_mod)
    hold_m = _hold_mesh(got["rows"])
    fold_m = _fold_mesh(got["rows"])
    assert got["replay_seal"] == _replay_seal(
        got["mesh_digest"], got["auth_stamp"], epoch, hold_m, fold_m
    )
    assert got["replay_seal"] != _replay_seal(
        got["mesh_digest"], got["auth_stamp"], epoch, hold_m, 0
    )
    duty4_stamp = 0
    for row in sorted(got["rows"], key=lambda r: r["row_id"]):
        meta = rows_in[row["row_id"]]
        hk = int(row["hop_key"], 16)
        if row["arm"] == "hold":
            base = {1: 3, 2: 5, 3: 7, 4: 11}[meta["pad"]]
            rot = base + (epoch % 4)
        else:
            rot = meta["pad"]
        duty4_stamp ^= _rotl64(hk, rot) ^ row["fold_tag"] ^ row["span_u64"]
    duty4_stamp ^= DUTY_MIX
    if any(
        (_stamp_rotate("hold", p, epoch) != ({1: 3, 2: 5, 3: 7, 4: 11}[p] + (epoch % 4)))
        for p in (1, 2, 3, 4)
    ) or any(_stamp_rotate("train", p, epoch) != p for p in (1, 2, 3, 4)):
        assert got["auth_stamp"] != _hex16(duty4_stamp)


def _assert_full_contract() -> None:
    exp = _expected()
    got = _read_out()
    seal = _read_seal()
    assert got["mesh_digest"] == exp["mesh_digest"]
    assert got["auth_stamp"] == exp["auth_stamp"]
    assert got["replay_seal"] == exp["replay_seal"]
    assert seal["epoch"] == exp["epoch"]
    assert seal["seal_hex"] == exp["replay_seal"]
    assert len(got["rows"]) == len(exp["rows"])
    for row, er in zip(
        sorted(got["rows"], key=lambda r: r["row_id"]),
        sorted(exp["rows"], key=lambda r: r["row_id"]),
        strict=True,
    ):
        assert row["hop_key"] == er["hop_key"]
        assert row["fold_tag"] == er["fold_tag"]
        assert row["span_u64"] == er["span_u64"]
        assert row["join_hex"] == er["join_hex"]
        assert row["arm"] == er["arm"]
        assert _envelope_ok(row["arm"], row["span_u64"])
    _assert_rejects_near_misses(got, exp["epoch"])


def test_k41_mesh_pin_poison() -> None:
    """A leftover side/mesh.pin must not alter mesh, stamp, or seal after regeneration."""
    _rebuild_and_run()
    (SIDE / "mesh.pin").write_text(str((1 << 64) - 1), encoding="utf-8")
    _rebuild_and_run()
    _assert_full_contract()


def test_k42_train_rotate_fixed_one() -> None:
    """Train stamp rotates must use width 1 on every pad, not the pad index."""
    epoch = _epoch()
    for pad in (1, 2, 3, 4):
        assert _stamp_rotate("train", pad, epoch) == 1
    _rebuild_and_run()
    assert _read_out()["auth_stamp"] == _expected()["auth_stamp"]


def test_k43_epoch_ladder() -> None:
    """Successive annex epoch bumps with journal poison must retarget stamp and seal each step."""
    manifest = MANIFEST
    original = manifest.read_text(encoding="utf-8")
    try:
        _rebuild_and_run()
        cur = _epoch()
        prev_stamp = _read_out()["auth_stamp"]
        prev_seal = _read_out()["replay_seal"]
        prev_mesh = _read_out()["mesh_digest"]
        for step in range(1, 6):
            new_epoch = cur + 1
            while True:
                if (
                    (new_epoch & 0xFF) != (cur & 0xFF)
                    and new_epoch % 3 != cur % 3
                    and new_epoch % 3 != 0
                    and new_epoch % 5 != cur % 5
                    and new_epoch % 7 != cur % 7
                    and _hold_envelopes_ok_for_epoch(new_epoch)
                ):
                    break
                new_epoch += 1
                if new_epoch > cur + 500:
                    raise AssertionError("no envelope-safe epoch found")
            text = manifest.read_text(encoding="utf-8")
            manifest.write_text(
                text.replace(f'"epoch": {cur}', f'"epoch": {new_epoch}'),
                encoding="utf-8",
            )
            jrn = SIDE / "jrn"
            jrn.mkdir(parents=True, exist_ok=True)
            (jrn / "epoch.snap").write_text(str(cur), encoding="utf-8")
            (jrn / "seal.hint").write_text(str(7 + step), encoding="utf-8")
            (SIDE / "mesh.pin").write_text(str(9 + step), encoding="utf-8")
            (SIDE / "fold.soft").write_text("1", encoding="utf-8")
            (SIDE / "span.soft").write_text("1", encoding="utf-8")
            (SIDE / "stamp.soft").write_text(str(11 + step), encoding="utf-8")
            _write_duty_cache([("hold:1", step), ("train:4", 20 + step)])
            _write_hop_cache(_bound_seed() ^ step, [("t01", step), ("h01", 100 + step)])
            _rebuild_and_run()
            exp = _expected()
            got = _read_out()
            assert exp["epoch"] == new_epoch
            assert got["auth_stamp"] == exp["auth_stamp"]
            assert got["replay_seal"] == exp["replay_seal"]
            assert got["mesh_digest"] == exp["mesh_digest"]
            assert _read_seal()["epoch"] == new_epoch
            assert got["auth_stamp"] != prev_stamp
            assert got["replay_seal"] != prev_seal
            assert got["mesh_digest"] != prev_mesh
            _assert_full_contract()
            prev_stamp = got["auth_stamp"]
            prev_seal = got["replay_seal"]
            prev_mesh = got["mesh_digest"]
            cur = new_epoch
    finally:
        manifest.write_text(original, encoding="utf-8")
        _rebuild_and_run()


def test_k44_alternating_side_poison() -> None:
    """Alternating hop.cache, mesh.pin, and journal poisons across runs must stay live."""
    _rebuild_and_run()

    def poison_cache() -> None:
        (SIDE / "hop.cache").write_text("seed=0\nx=1\n", encoding="utf-8")

    def poison_pin() -> None:
        (SIDE / "mesh.pin").write_text("12345", encoding="utf-8")

    def poison_journal() -> None:
        (SIDE / "jrn").mkdir(parents=True, exist_ok=True)
        (SIDE / "jrn" / "seal.hint").write_text("99", encoding="utf-8")
        (SIDE / "jrn" / "epoch.snap").write_text(str(_epoch() + 6), encoding="utf-8")

    def poison_mixed() -> None:
        _write_hop_cache(_bound_seed(), [("t01", 1), ("h01", 2)])
        (SIDE / "mesh.pin").write_text("999", encoding="utf-8")
        (SIDE / "fold.soft").write_text("1", encoding="utf-8")
        (SIDE / "span.soft").write_text("1", encoding="utf-8")

    for poison in (poison_cache, poison_pin, poison_journal, poison_mixed):
        poison()
        _rebuild_and_run()
        _assert_full_contract()


def test_k45_holdout_after_triple_stress() -> None:
    """Hold rows on every pad must stay correct after cache, pin, and journal stress."""
    _rebuild_and_run()
    (SIDE / "hop.cache").write_text("seed=1\nbad=1\n", encoding="utf-8")
    (SIDE / "mesh.pin").write_text("42", encoding="utf-8")
    (SIDE / "fold.soft").write_text("1", encoding="utf-8")
    (SIDE / "span.soft").write_text("1", encoding="utf-8")
    jrn = SIDE / "jrn"
    jrn.mkdir(parents=True, exist_ok=True)
    (jrn / "seal.hint").write_text("3", encoding="utf-8")
    (jrn / "epoch.snap").write_text(str(_epoch() + 8), encoding="utf-8")
    _rebuild_and_run()
    exp = {r["row_id"]: r for r in _expected()["rows"] if r["arm"] == "hold"}
    got = {r["row_id"]: r for r in _read_out()["rows"] if r["arm"] == "hold"}
    assert {er["pad"] for er in exp.values()} == {1, 2, 3, 4}
    for rid, er in exp.items():
        assert got[rid]["fold_tag"] == er["fold_tag"]
        assert got[rid]["hop_key"] == er["hop_key"]
        assert got[rid]["span_u64"] == er["span_u64"]
        assert _envelope_ok("hold", got[rid]["span_u64"])
    assert _read_out()["auth_stamp"] == _expected()["auth_stamp"]
    assert _read_out()["replay_seal"] == _expected()["replay_seal"]


def test_k46_overflow_hold_folds() -> None:
    """Hold rows whose lo times w overflows 32 bits must still match fold_home tags."""
    wide = [r for r in _load_rows() if r["arm"] == 1 and (r["lo"] * r["w"]) > 0xFFFFFFFF]
    assert len(wide) >= 2, "fixture must include multiple overflow hold rows"
    exp = {r["row_id"]: r for r in _expected()["rows"]}
    got = {r["row_id"]: r for r in _read_out()["rows"]}
    for r in wide:
        assert got[r["id"]]["fold_tag"] == exp[r["id"]]["fold_tag"]


def test_k47_epoch_bounce() -> None:
    """Advance epoch, regen, then restore the original epoch; seals must bounce with it."""
    manifest = MANIFEST
    original = manifest.read_text(encoding="utf-8")
    try:
        _rebuild_and_run()
        base = _epoch()
        first = _read_out()["replay_seal"]
        new_epoch = base + 5
        manifest.write_text(
            original.replace(f'"epoch": {base}', f'"epoch": {new_epoch}'),
            encoding="utf-8",
        )
        (SIDE / "jrn").mkdir(parents=True, exist_ok=True)
        (SIDE / "jrn" / "epoch.snap").write_text(str(base), encoding="utf-8")
        _rebuild_and_run()
        mid = _read_out()
        assert mid["replay_seal"] == _expected()["replay_seal"]
        manifest.write_text(original, encoding="utf-8")
        (SIDE / "mesh.pin").write_text("77", encoding="utf-8")
        (SIDE / "jrn" / "seal.hint").write_text("88", encoding="utf-8")
        (SIDE / "fold.soft").write_text("1", encoding="utf-8")
        _rebuild_and_run()
        _assert_full_contract()
        assert _read_out()["replay_seal"] == first
    finally:
        manifest.write_text(original, encoding="utf-8")
        _rebuild_and_run()


def test_k48_seal_duty_identity_after_pin() -> None:
    """replay_seal must keep the duty_home identity after mesh.pin and seal.hint stress."""
    _rebuild_and_run()
    (SIDE / "mesh.pin").write_text(str(int(_read_out()["mesh_digest"], 16)), encoding="utf-8")
    (SIDE / "jrn").mkdir(parents=True, exist_ok=True)
    (SIDE / "jrn" / "seal.hint").write_text(
        str(int(_read_out()["replay_seal"], 16) ^ 0xFF), encoding="utf-8"
    )
    _rebuild_and_run()
    got = _read_out()
    seal = _read_seal()
    derived = _replay_seal(
        got["mesh_digest"],
        got["auth_stamp"],
        seal["epoch"],
        _hold_mesh(got["rows"]),
        _fold_mesh(got["rows"]),
    )
    assert got["replay_seal"] == derived
    assert seal["seal_hex"] == derived
    assert derived == _expected()["replay_seal"]


def test_k49_fold_soft_marker() -> None:
    """A planted fold.soft marker must not downgrade hold folds on the next regeneration."""
    _rebuild_and_run()
    (SIDE / "fold.soft").write_text("1", encoding="utf-8")
    (SIDE / "span.soft").write_text("1", encoding="utf-8")
    (SIDE / "mesh.pin").write_text("9", encoding="utf-8")
    jrn = SIDE / "jrn"
    jrn.mkdir(parents=True, exist_ok=True)
    (jrn / "epoch.snap").write_text(str(_epoch() + 3), encoding="utf-8")
    (jrn / "seal.hint").write_text("11", encoding="utf-8")
    _rebuild_and_run()
    _assert_full_contract()
    exp = {r["row_id"]: r for r in _expected()["rows"] if r["arm"] == "hold"}
    got = {r["row_id"]: r for r in _read_out()["rows"] if r["arm"] == "hold"}
    for rid, er in exp.items():
        assert got[rid]["fold_tag"] == er["fold_tag"]
        assert got[rid]["hop_key"] == er["hop_key"]
        assert got[rid]["span_u64"] == er["span_u64"]
    assert _read_out()["replay_seal"] == _expected()["replay_seal"]


def test_k50_span_soft_marker() -> None:
    """A planted span.soft marker must not replace hold spans with width-only values."""
    _rebuild_and_run()
    (SIDE / "span.soft").write_text("1", encoding="utf-8")
    (SIDE / "fold.soft").write_text("1", encoding="utf-8")
    jrn = SIDE / "jrn"
    jrn.mkdir(parents=True, exist_ok=True)
    (jrn / "seal.hint").write_text("3", encoding="utf-8")
    _rebuild_and_run()
    _assert_full_contract()
    exp = {r["row_id"]: r for r in _expected()["rows"] if r["arm"] == "hold"}
    got = {r["row_id"]: r for r in _read_out()["rows"] if r["arm"] == "hold"}
    for rid, er in exp.items():
        assert got[rid]["span_u64"] == er["span_u64"]
        assert got[rid]["hop_key"] == er["hop_key"]
        assert _envelope_ok("hold", got[rid]["span_u64"])


def test_k51_second_pass_hold_stable() -> None:
    """Second uxr pass must keep hold fold/span identities after side sketches accumulate."""
    _rebuild_and_run()
    first = {
        r["row_id"]: (r["hop_key"], r["fold_tag"], r["span_u64"])
        for r in _read_out()["rows"]
        if r["arm"] == "hold"
    }
    (SIDE / "fold.soft").write_text("1", encoding="utf-8")
    (SIDE / "span.soft").write_text("1", encoding="utf-8")
    _rebuild_and_run()
    second = {
        r["row_id"]: (r["hop_key"], r["fold_tag"], r["span_u64"])
        for r in _read_out()["rows"]
        if r["arm"] == "hold"
    }
    assert first == second
    _assert_full_contract()


def test_k52_hold_fold_epoch_latch() -> None:
    """Hold fold tags and hop_keys must retarget when annex epoch changes live latches."""
    manifest = MANIFEST
    original = manifest.read_text(encoding="utf-8")
    try:
        _rebuild_and_run()
        base = _epoch()
        before = {
            r["row_id"]: (r["hop_key"], r["fold_tag"])
            for r in _read_out()["rows"]
            if r["arm"] == "hold"
        }
        # Change E mod 3 and the low-8 walk latch together when possible.
        new_epoch = base + 1
        while new_epoch % 3 == base % 3 or (new_epoch & 0xFF) == (base & 0xFF):
            new_epoch += 1
        manifest.write_text(
            original.replace(f'"epoch": {base}', f'"epoch": {new_epoch}'),
            encoding="utf-8",
        )
        (SIDE / "jrn").mkdir(parents=True, exist_ok=True)
        (SIDE / "jrn" / "epoch.snap").write_text(str(base), encoding="utf-8")
        (SIDE / "fold.soft").write_text("1", encoding="utf-8")
        (SIDE / "span.soft").write_text("1", encoding="utf-8")
        _write_hop_cache(_bound_seed(), [("t01", 1), ("h01", 2)])
        _rebuild_and_run()
        exp = _expected()
        got = _read_out()
        after = {
            r["row_id"]: (r["hop_key"], r["fold_tag"])
            for r in got["rows"]
            if r["arm"] == "hold"
        }
        assert after == {
            r["row_id"]: (r["hop_key"], r["fold_tag"])
            for r in exp["rows"]
            if r["arm"] == "hold"
        }
        assert after != before
        assert got["mesh_digest"] == exp["mesh_digest"]
        assert got["auth_stamp"] == exp["auth_stamp"]
        assert got["replay_seal"] == exp["replay_seal"]
    finally:
        manifest.write_text(original, encoding="utf-8")
        _rebuild_and_run()


def test_k53_fold_mod_not_stamp_mod() -> None:
    """Hold fold epoch latch must use mod 3, not the stamp duty mod 5."""
    epoch = _epoch()
    assert _hold_rotate(1, epoch) == 13 + (epoch % 3)
    assert _hold_rotate(4, epoch) == 29 + (epoch % 3)
    assert _stamp_rotate("hold", 1, epoch) == 3 + (epoch % 5)
    assert _stamp_rotate("hold", 4, epoch) == 11 + (epoch % 5)
    # Across a short epoch window, mod-3 and mod-5 hold widths diverge.
    diverged = False
    for delta in range(1, 16):
        e2 = epoch + delta
        if _hold_rotate(1, e2) - _hold_rotate(1, epoch) != _stamp_rotate(
            "hold", 1, e2
        ) - _stamp_rotate("hold", 1, epoch):
            diverged = True
            break
    assert diverged
    assert any((13 + (e % 3)) != (13 + (e % 5)) for e in range(epoch, epoch + 5))
    _rebuild_and_run()
    assert _read_out()["auth_stamp"] == _expected()["auth_stamp"]
    hold = [r for r in _read_out()["rows"] if r["arm"] == "hold"]
    exp = {r["row_id"]: r for r in _expected()["rows"] if r["arm"] == "hold"}
    for r in hold:
        assert r["fold_tag"] == exp[r["row_id"]]["fold_tag"]
    manifest = MANIFEST
    original = manifest.read_text(encoding="utf-8")
    try:
        base = epoch
        new_epoch = base + 1
        while True:
            if (
                (new_epoch % 3) != (base % 3)
                and (new_epoch % 5) != (base % 5)
                and (13 + (new_epoch % 3)) != (13 + (new_epoch % 5))
                and _hold_envelopes_ok_for_epoch(new_epoch)
            ):
                break
            new_epoch += 1
            if new_epoch > base + 400:
                raise AssertionError("no mod3/mod5 diverge epoch")
        manifest.write_text(
            original.replace(f'"epoch": {base}', f'"epoch": {new_epoch}'),
            encoding="utf-8",
        )
        (SIDE / "fold.soft").write_text("1", encoding="utf-8")
        (SIDE / "stamp.soft").write_text("21", encoding="utf-8")
        _write_duty_cache([("hold:1", 4), ("hold:4", 9)])
        _rebuild_and_run()
        _assert_full_contract()
        after_hold = {
            r["row_id"]: r["fold_tag"] for r in _read_out()["rows"] if r["arm"] == "hold"
        }
        assert after_hold == {
            r["row_id"]: r["fold_tag"] for r in _expected()["rows"] if r["arm"] == "hold"
        }
        # Fold rotate moved with mod 3, not mod 5.
        assert _hold_rotate(1, new_epoch) == 13 + (new_epoch % 3)
        assert _hold_rotate(1, new_epoch) != 13 + (new_epoch % 5)
    finally:
        manifest.write_text(original, encoding="utf-8")
        _rebuild_and_run()


def test_k54_hold_walk_epoch_latch() -> None:
    """Hold hop walks must use S xor ((E plus pad) and 0xff); train keeps unbound S."""
    epoch = _epoch()
    seed = _bound_seed()
    for pad in (1, 2, 3, 4):
        train = _hop_digest(pad, seed, arm=0, epoch=epoch)
        hold = _hop_digest(pad, seed, arm=1, epoch=epoch)
        assert train == _hop_digest(pad, seed, arm=0, epoch=epoch + 7)
        flat = _hop_digest(pad, seed ^ (epoch & 0xFF), arm=0, epoch=epoch)
        product = _hop_digest(
            pad, seed ^ _hold_walk_product_false_green(epoch, pad), arm=0, epoch=epoch
        )
        summed = _hop_digest(
            pad, seed ^ _hold_walk_mix(epoch, pad), arm=0, epoch=epoch
        )
        assert hold == summed
        assert hold != train
        if _hold_walk_mix(epoch, pad) != (epoch & 0xFF):
            assert hold != flat
        if _hold_walk_mix(epoch, pad) != _hold_walk_product_false_green(epoch, pad):
            assert hold != product
        assert hold != _short_hop_digest(pad, seed ^ _hold_walk_mix(epoch, pad))
    if _hold_walk_mix(epoch, 1) != _hold_walk_mix(epoch, 4):
        assert _hop_digest(1, seed, arm=1, epoch=epoch) != _hop_digest(
            4, seed, arm=1, epoch=epoch
        )
    manifest = MANIFEST
    original = manifest.read_text(encoding="utf-8")
    try:
        _rebuild_and_run()
        base = _epoch()
        before = {
            r["row_id"]: r["hop_key"]
            for r in _read_out()["rows"]
            if r["arm"] == "hold"
        }
        new_epoch = base + 1
        while (new_epoch & 0xFF) == (base & 0xFF):
            new_epoch += 1
        manifest.write_text(
            original.replace(f'"epoch": {base}', f'"epoch": {new_epoch}'),
            encoding="utf-8",
        )
        (SIDE / "jrn").mkdir(parents=True, exist_ok=True)
        (SIDE / "jrn" / "epoch.snap").write_text(str(base), encoding="utf-8")
        (SIDE / "fold.soft").write_text("1", encoding="utf-8")
        _rebuild_and_run()
        exp = _expected()
        got = _read_out()
        after = {
            r["row_id"]: r["hop_key"] for r in got["rows"] if r["arm"] == "hold"
        }
        assert after == {
            r["row_id"]: r["hop_key"] for r in exp["rows"] if r["arm"] == "hold"
        }
        assert after != before
        train_got = {
            r["row_id"]: r["hop_key"] for r in got["rows"] if r["arm"] == "train"
        }
        train_exp = {
            r["row_id"]: r["hop_key"] for r in exp["rows"] if r["arm"] == "train"
        }
        assert train_got == train_exp
        _assert_full_contract()
    finally:
        manifest.write_text(original, encoding="utf-8")
        _rebuild_and_run()


def test_k55_hold_mesh_seal_binding() -> None:
    """replay_seal must xor hold_mesh; epoch moves that retarget hold hops must retarget seal."""
    _rebuild_and_run()
    got = _read_out()
    hold = _hold_mesh(got["rows"])
    assert hold != 0
    assert got["replay_seal"] == _replay_seal(
        got["mesh_digest"], got["auth_stamp"], _epoch(), hold, _fold_mesh(got["rows"])
    )
    manifest = MANIFEST
    original = manifest.read_text(encoding="utf-8")
    try:
        base = _epoch()
        before_seal = got["replay_seal"]
        before_hold = {
            r["row_id"]: r["hop_key"] for r in got["rows"] if r["arm"] == "hold"
        }
        new_epoch = base + 1
        while (new_epoch & 0xFF) == (base & 0xFF):
            new_epoch += 1
        manifest.write_text(
            original.replace(f'"epoch": {base}', f'"epoch": {new_epoch}'),
            encoding="utf-8",
        )
        (SIDE / "jrn").mkdir(parents=True, exist_ok=True)
        (SIDE / "jrn" / "epoch.snap").write_text(str(base), encoding="utf-8")
        (SIDE / "fold.soft").write_text("1", encoding="utf-8")
        (SIDE / "span.soft").write_text("1", encoding="utf-8")
        (SIDE / "mesh.pin").write_text("5", encoding="utf-8")
        _rebuild_and_run()
        exp = _expected()
        after = _read_out()
        after_hold = {
            r["row_id"]: r["hop_key"] for r in after["rows"] if r["arm"] == "hold"
        }
        assert after_hold != before_hold
        assert after["replay_seal"] == exp["replay_seal"]
        assert after["replay_seal"] != before_seal
        assert after["replay_seal"] == _replay_seal(
            after["mesh_digest"],
            after["auth_stamp"],
            new_epoch,
            _hold_mesh(after["rows"]),
            _fold_mesh(after["rows"]),
        )
    finally:
        manifest.write_text(original, encoding="utf-8")
        _rebuild_and_run()


def test_k56_fold_mix_byte_beyond_mod3() -> None:
    """Hold folds must move when E and 0xff changes even if E mod 3 stays fixed."""
    manifest = MANIFEST
    original = manifest.read_text(encoding="utf-8")
    try:
        _rebuild_and_run()
        base = _epoch()
        before = {
            r["row_id"]: r["fold_tag"]
            for r in _read_out()["rows"]
            if r["arm"] == "hold"
        }
        new_epoch = base + 3
        while (new_epoch & 0xFF) == (base & 0xFF):
            new_epoch += 3
        assert new_epoch % 3 == base % 3
        manifest.write_text(
            original.replace(f'"epoch": {base}', f'"epoch": {new_epoch}'),
            encoding="utf-8",
        )
        (SIDE / "fold.soft").write_text("1", encoding="utf-8")
        (SIDE / "jrn").mkdir(parents=True, exist_ok=True)
        (SIDE / "jrn" / "seal.hint").write_text("4", encoding="utf-8")
        _rebuild_and_run()
        exp = _expected()
        after = {
            r["row_id"]: r["fold_tag"]
            for r in _read_out()["rows"]
            if r["arm"] == "hold"
        }
        assert after == {
            r["row_id"]: r["fold_tag"] for r in exp["rows"] if r["arm"] == "hold"
        }
        assert after != before
        assert _read_out()["replay_seal"] == exp["replay_seal"]
        assert _hold_rotate(1, new_epoch) == _hold_rotate(1, base)
    finally:
        manifest.write_text(original, encoding="utf-8")
        _rebuild_and_run()


def test_k57_duty_cache_poison() -> None:
    """A planted duty.cache must not freeze auth_stamp rotate widths."""
    _rebuild_and_run()
    _write_duty_cache(
        [
            ("train:1", 9),
            ("hold:1", 99),
            ("hold:2", 98),
            ("hold:3", 97),
            ("hold:4", 96),
        ]
    )
    (SIDE / "fold.soft").write_text("1", encoding="utf-8")
    (SIDE / "jrn").mkdir(parents=True, exist_ok=True)
    (SIDE / "jrn" / "seal.hint").write_text("6", encoding="utf-8")
    _rebuild_and_run()
    _assert_full_contract()
    assert _read_out()["auth_stamp"] == _expected()["auth_stamp"]
    assert _read_out()["replay_seal"] == _expected()["replay_seal"]


def test_k58_mesh_compose_epoch_latch() -> None:
    """mesh_digest must use rotl(train_mesh xor hold_mesh, E mod 3) across epoch moves."""
    manifest = MANIFEST
    original = manifest.read_text(encoding="utf-8")
    try:
        _rebuild_and_run()
        base = _epoch()
        before = _read_out()["mesh_digest"]
        new_epoch = base + 1
        while new_epoch % 3 == base % 3:
            new_epoch += 1
        manifest.write_text(
            original.replace(f'"epoch": {base}', f'"epoch": {new_epoch}'),
            encoding="utf-8",
        )
        _write_duty_cache([("hold:1", 1)])
        (SIDE / "mesh.pin").write_text("3", encoding="utf-8")
        (SIDE / "span.soft").write_text("1", encoding="utf-8")
        (SIDE / "jrn").mkdir(parents=True, exist_ok=True)
        (SIDE / "jrn" / "epoch.snap").write_text(str(base), encoding="utf-8")
        _rebuild_and_run()
        exp = _expected()
        got = _read_out()
        assert got["mesh_digest"] == exp["mesh_digest"]
        assert got["mesh_digest"] != before or (base % 3 == new_epoch % 3)
        train = 0
        hold = 0
        for row in sorted(got["rows"], key=lambda r: r["row_id"]):
            hk = int(row["hop_key"], 16)
            if row["arm"] == "hold":
                hold ^= hk
            else:
                train ^= hk
        assert got["mesh_digest"] == _hex16(
            _rotl64(train ^ hold, _mesh_width(new_epoch)) & 0xFFFFFFFFFFFFFFFF
        )
        assert got["mesh_digest"] != _hex16(
            (_rotl64(train, _mesh_width(new_epoch)) ^ hold) & 0xFFFFFFFFFFFFFFFF
        )
        assert got["auth_stamp"] == exp["auth_stamp"]
        assert got["replay_seal"] == exp["replay_seal"]
        for row in got["rows"]:
            if row["arm"] == "hold":
                assert _envelope_ok("hold", row["span_u64"])
                assert row["span_u64"] == next(
                    er["span_u64"] for er in exp["rows"] if er["row_id"] == row["row_id"]
                )
    finally:
        manifest.write_text(original, encoding="utf-8")
        _rebuild_and_run()


def test_k59_hold_join_epoch_byte() -> None:
    """Hold join_hex must mix shifted epoch and pad; train joins stay bare arm_bit form."""
    _rebuild_and_run()
    epoch = _epoch()
    exp = {r["row_id"]: r for r in _expected()["rows"]}
    for row in _read_out()["rows"]:
        assert row["join_hex"] == exp[row["row_id"]]["join_hex"]
        hk = int(row["hop_key"], 16)
        arm_bit = 0 if row["arm"] == "train" else 1
        bare = (hk ^ row["fold_tag"] ^ row["span_u64"] ^ arm_bit) & 0xFFFFFFFFFFFFFFFF
        if row["arm"] == "train":
            assert int(row["join_hex"], 16) == bare
        else:
            pad = next(r["pad"] for r in _load_rows() if r["id"] == row["row_id"])
            assert int(row["join_hex"], 16) == (
                bare ^ _hold_join_mix(epoch, pad)
            )
    manifest = MANIFEST
    original = manifest.read_text(encoding="utf-8")
    try:
        base = _epoch()
        before = {
            r["row_id"]: r["join_hex"]
            for r in _read_out()["rows"]
            if r["arm"] == "hold"
        }
        new_epoch = base + 1
        while (new_epoch & 0xFF) == (base & 0xFF):
            new_epoch += 1
        manifest.write_text(
            original.replace(f'"epoch": {base}', f'"epoch": {new_epoch}'),
            encoding="utf-8",
        )
        (SIDE / "jrn").mkdir(parents=True, exist_ok=True)
        (SIDE / "jrn" / "seal.hint").write_text("9", encoding="utf-8")
        _rebuild_and_run()
        after = {
            r["row_id"]: r["join_hex"]
            for r in _read_out()["rows"]
            if r["arm"] == "hold"
        }
        assert after == {
            r["row_id"]: r["join_hex"]
            for r in _expected()["rows"]
            if r["arm"] == "hold"
        }
        assert after != before
    finally:
        manifest.write_text(original, encoding="utf-8")
        _rebuild_and_run()


def test_k60_walk_pad_scale_not_flat() -> None:
    """Hold walks must reject flat (E and 0xff) seeds when pad scale differs."""
    _rebuild_and_run()
    epoch = _epoch()
    seed = _bound_seed()
    got = {r["row_id"]: r for r in _read_out()["rows"] if r["arm"] == "hold"}
    rows = [r for r in _load_rows() if r["arm"] != 0]
    diverged = False
    for r in rows:
        flat = _hex16(
            _hop_digest(r["pad"], seed ^ (epoch & 0xFF), arm=0, epoch=epoch)
        )
        product = _hex16(
            _hop_digest(r["pad"], seed ^ ((epoch * r["pad"]) & 0xFF), arm=0, epoch=epoch)
        )
        live = got[r["id"]]["hop_key"]
        if flat != live or product != live:
            diverged = True
        assert live == _hex16(_hop_digest(r["pad"], seed, arm=1, epoch=epoch))
        if _hold_walk_mix(epoch, r["pad"]) != _hold_walk_product_false_green(
            epoch, r["pad"]
        ):
            assert live != product
        if _hold_walk_mix(epoch, r["pad"]) != (epoch & 0xFF):
            assert live != flat
    assert diverged
    (SIDE / "hop.cache").write_text("seed=9\nx=1\n", encoding="utf-8")
    (SIDE / "fold.soft").write_text("1", encoding="utf-8")
    _rebuild_and_run()
    _assert_full_contract()
    _assert_rejects_near_misses()


def test_k61_seal_hold_mesh_duty_rotate() -> None:
    """replay_seal must rotl hold_mesh by 3+(E mod 5), not xor raw hold_mesh."""
    _rebuild_and_run()
    got = _read_out()
    epoch = _epoch()
    hold = _hold_mesh(got["rows"])
    assert got["replay_seal"] == _replay_seal(
        got["mesh_digest"], got["auth_stamp"], epoch, hold, _fold_mesh(got["rows"])
    )
    raw = (
        _rotl64(int(got["mesh_digest"], 16), 5)
        ^ int(got["auth_stamp"], 16)
        ^ ((epoch & 0xFFFFFFFF) << 16)
        ^ DUTY_MIX
        ^ _rotl64(hold, 3 + (epoch % 5))
    )
    if hold != 0 or _fold_mesh(got["rows"]) != 0:
        assert got["replay_seal"] != _hex16(raw)
    no_fold = _replay_seal(got["mesh_digest"], got["auth_stamp"], epoch, hold, 0)
    if _fold_mesh(got["rows"]) != 0:
        assert got["replay_seal"] != no_fold
    manifest = MANIFEST
    original = manifest.read_text(encoding="utf-8")
    try:
        base = epoch
        new_epoch = base + 1
        while (3 + (new_epoch % 5)) == (3 + (base % 5)):
            new_epoch += 1
        manifest.write_text(
            original.replace(f'"epoch": {base}', f'"epoch": {new_epoch}'),
            encoding="utf-8",
        )
        _write_duty_cache([("hold:2", 1)])
        (SIDE / "mesh.pin").write_text("7", encoding="utf-8")
        _rebuild_and_run()
        after = _read_out()
        assert after["replay_seal"] == _expected()["replay_seal"]
        assert after["replay_seal"] == _replay_seal(
            after["mesh_digest"],
            after["auth_stamp"],
            new_epoch,
            _hold_mesh(after["rows"]),
            _fold_mesh(after["rows"]),
        )
    finally:
        manifest.write_text(original, encoding="utf-8")
        _rebuild_and_run()


def test_k62_fold_pad_shift_mix() -> None:
    """Hold folds must include (pad left-shift 16) in padMix beyond epoch byte."""
    _rebuild_and_run()
    epoch = _epoch()
    rows_in = {r["id"]: r for r in _load_rows()}
    for row in _read_out()["rows"]:
        if row["arm"] != "hold":
            continue
        meta = rows_in[row["row_id"]]
        h = int(row["hop_key"], 16)
        full = _exact(h, meta["pad"], 1, meta["lo"], meta["hi"], meta["w"], epoch)
        assert row["fold_tag"] == full
        # Without pad<<16 the prior false-green composition must diverge.
        base = ((h & 0xFFFFFFFF) ^ (meta["lo"] * meta["w"])) & 0xFFFFFFFFFFFF
        shallow_mix = (meta["pad"] * 0xA5A5) ^ (epoch & 0xFF) ^ (meta["pad"] << 16)
        prior = (
            _rotl64(base, _hold_rotate(meta["pad"], epoch)) ^ meta["hi"] ^ shallow_mix
        ) & 0xFFFFFFFFFFFF
        assert row["fold_tag"] != prior


def test_k63_span_pad_xor_epoch() -> None:
    """Hold spans must xor pad into the epoch loTerm mix."""
    _rebuild_and_run()
    epoch = _epoch()
    rows_in = {r["id"]: r for r in _load_rows()}
    for row in _read_out()["rows"]:
        if row["arm"] != "hold":
            continue
        meta = rows_in[row["row_id"]]
        h = int(row["hop_key"], 16)
        assert row["span_u64"] == _span(
            h, meta["lo"], meta["hi"], meta["w"], arm=1, epoch=epoch, pad=meta["pad"]
        )
        if meta["pad"] != 0:
            flat_only = (
                (
                    ((meta["hi"] - meta["lo"]) & 0xFFFFFFFF) * 0x9E3779B9
                )
                ^ (h & 0xFFFFFFFF)
                ^ (
                    (((meta["lo"] & 0xFFFFFFFF) << 1) ^ (meta["w"] & 0xFFFFFFFF))
                    ^ (epoch & 0xFF)
                    ^ meta["pad"]
                )
            ) & 0xFFFFFFFFFFFFFFFF
            assert row["span_u64"] != flat_only


def test_k64_coupled_epoch_quad() -> None:
    """One epoch move must retarget hold hop, join, mesh, and seal together."""
    manifest = MANIFEST
    original = manifest.read_text(encoding="utf-8")
    try:
        _rebuild_and_run()
        base = _epoch()
        before = _read_out()
        new_epoch = base + 1
        while (
            (new_epoch & 0xFF) == (base & 0xFF)
            or new_epoch % 3 == base % 3
            or new_epoch % 5 == base % 5
        ):
            new_epoch += 1
        manifest.write_text(
            original.replace(f'"epoch": {base}', f'"epoch": {new_epoch}'),
            encoding="utf-8",
        )
        _write_duty_cache([("train:1", 4), ("hold:4", 2)])
        (SIDE / "fold.soft").write_text("1", encoding="utf-8")
        (SIDE / "span.soft").write_text("1", encoding="utf-8")
        (SIDE / "mesh.pin").write_text("11", encoding="utf-8")
        (SIDE / "jrn").mkdir(parents=True, exist_ok=True)
        (SIDE / "jrn" / "epoch.snap").write_text(str(base), encoding="utf-8")
        (SIDE / "jrn" / "seal.hint").write_text("12", encoding="utf-8")
        _rebuild_and_run()
        exp = _expected()
        after = _read_out()
        assert after["mesh_digest"] == exp["mesh_digest"]
        assert after["auth_stamp"] == exp["auth_stamp"]
        assert after["replay_seal"] == exp["replay_seal"]
        assert after["mesh_digest"] != before["mesh_digest"]
        assert after["replay_seal"] != before["replay_seal"]
        hold_before = {
            r["row_id"]: (r["hop_key"], r["join_hex"], r["fold_tag"], r["span_u64"])
            for r in before["rows"]
            if r["arm"] == "hold"
        }
        hold_after = {
            r["row_id"]: (r["hop_key"], r["join_hex"], r["fold_tag"], r["span_u64"])
            for r in after["rows"]
            if r["arm"] == "hold"
        }
        assert hold_after != hold_before
        for rid, vals in hold_after.items():
            assert vals == (
                next(r["hop_key"] for r in exp["rows"] if r["row_id"] == rid),
                next(r["join_hex"] for r in exp["rows"] if r["row_id"] == rid),
                next(r["fold_tag"] for r in exp["rows"] if r["row_id"] == rid),
                next(r["span_u64"] for r in exp["rows"] if r["row_id"] == rid),
            )
    finally:
        manifest.write_text(original, encoding="utf-8")
        _rebuild_and_run()


def test_k65_mesh_rejects_hold_rotate_false_green() -> None:
    """mesh_digest must not match the prior hold-rotate false-green composition."""
    _rebuild_and_run()
    got = _read_out()
    epoch = _epoch()
    train = 0
    hold = 0
    for row in sorted(got["rows"], key=lambda r: r["row_id"]):
        hk = int(row["hop_key"], 16)
        if row["arm"] == "hold":
            hold ^= hk
        else:
            train ^= hk
    composed = _rotl64(train ^ hold, _mesh_width(epoch)) & 0xFFFFFFFFFFFFFFFF
    assert got["mesh_digest"] == _hex16(composed)
    false_green = (_rotl64(train, _mesh_width(epoch)) ^ hold) & 0xFFFFFFFFFFFFFFFF
    bare_mod = _rotl64(train ^ hold, epoch % 3) & 0xFFFFFFFFFFFFFFFF
    if train != 0 and hold != 0:
        assert got["mesh_digest"] != _hex16(false_green) or false_green == composed
        if bare_mod != composed:
            assert got["mesh_digest"] != _hex16(bare_mod)
    manifest = MANIFEST
    original = manifest.read_text(encoding="utf-8")
    try:
        base = epoch
        new_epoch = base + 1
        while new_epoch % 3 == base % 3 or not _hold_envelopes_ok_for_epoch(new_epoch):
            new_epoch += 1
            if new_epoch > base + 400:
                raise AssertionError("no envelope-safe epoch found")
        manifest.write_text(
            original.replace(f'"epoch": {base}', f'"epoch": {new_epoch}'),
            encoding="utf-8",
        )
        (SIDE / "mesh.pin").write_text("77", encoding="utf-8")
        (SIDE / "fold.soft").write_text("1", encoding="utf-8")
        (SIDE / "stamp.soft").write_text("13", encoding="utf-8")
        _rebuild_and_run()
        after = _read_out()
        exp = _expected()
        assert after["mesh_digest"] == exp["mesh_digest"]
        assert after["mesh_digest"] != got["mesh_digest"]
        train2 = 0
        hold2 = 0
        for row in sorted(after["rows"], key=lambda r: r["row_id"]):
            hk = int(row["hop_key"], 16)
            if row["arm"] == "hold":
                hold2 ^= hk
            else:
                train2 ^= hk
        composed2 = _rotl64(train2 ^ hold2, _mesh_width(new_epoch)) & 0xFFFFFFFFFFFFFFFF
        assert after["mesh_digest"] == _hex16(composed2)
        old2 = (_rotl64(train2, _mesh_width(new_epoch)) ^ hold2) & 0xFFFFFFFFFFFFFFFF
        bare2 = _rotl64(train2 ^ hold2, new_epoch % 3) & 0xFFFFFFFFFFFFFFFF
        if train2 != 0 and hold2 != 0:
            assert after["mesh_digest"] != _hex16(old2) or old2 == composed2
            if bare2 != composed2:
                assert after["mesh_digest"] != _hex16(bare2)
        _assert_full_contract()
    finally:
        manifest.write_text(original, encoding="utf-8")
        _rebuild_and_run()


def test_k66_alternating_join_and_duty_poison() -> None:
    """Alternating duty.cache and journal poisons must leave join and seal live."""
    _rebuild_and_run()
    for i in range(3):
        _write_duty_cache([("hold:1", 20 + i), ("train:2", 30 + i)])
        (SIDE / "jrn").mkdir(parents=True, exist_ok=True)
        (SIDE / "jrn" / "seal.hint").write_text(str(100 + i), encoding="utf-8")
        (SIDE / "mesh.pin").write_text(str(200 + i), encoding="utf-8")
        _rebuild_and_run()
        _assert_full_contract()
        epoch = _epoch()
        for row in _read_out()["rows"]:
            if row["arm"] != "hold":
                continue
            hk = int(row["hop_key"], 16)
            bare = (hk ^ row["fold_tag"] ^ row["span_u64"] ^ 1) & 0xFFFFFFFFFFFFFFFF
            pad = next(r["pad"] for r in _load_rows() if r["id"] == row["row_id"])
            assert int(row["join_hex"], 16) == (
                bare ^ _hold_join_mix(epoch, pad)
            )


def test_k67_fold_mesh_seal_binding() -> None:
    """replay_seal must bind rotl64(fold_mesh, 2+(E mod 7)); omitting fold_mesh must fail."""
    _rebuild_and_run()
    got = _read_out()
    epoch = _epoch()
    hold = _hold_mesh(got["rows"])
    fold = _fold_mesh(got["rows"])
    assert fold != 0
    assert got["replay_seal"] == _replay_seal(
        got["mesh_digest"], got["auth_stamp"], epoch, hold, fold
    )
    assert got["replay_seal"] != _replay_seal(
        got["mesh_digest"], got["auth_stamp"], epoch, hold, 0
    )
    # Bare E mod 7 fold rotate (missing the +2) must not match the live seal.
    bare_fold_seal = (
        _rotl64(int(got["mesh_digest"], 16), 5)
        ^ int(got["auth_stamp"], 16)
        ^ ((epoch & 0xFFFFFFFF) << 16)
        ^ DUTY_MIX
        ^ _rotl64(hold, 3 + (epoch % 5))
        ^ _rotl64(fold, epoch % 7)
    )
    assert got["replay_seal"] != _hex16(bare_fold_seal)
    manifest = MANIFEST
    original = manifest.read_text(encoding="utf-8")
    try:
        base = epoch
        new_epoch = base + 1
        while (new_epoch % 7) == (base % 7) or (new_epoch & 0xFF) == (base & 0xFF):
            new_epoch += 1
        manifest.write_text(
            original.replace(f'"epoch": {base}', f'"epoch": {new_epoch}'),
            encoding="utf-8",
        )
        (SIDE / "stamp.soft").write_text("99", encoding="utf-8")
        (SIDE / "fold.soft").write_text("1", encoding="utf-8")
        _rebuild_and_run()
        after = _read_out()
        assert after["replay_seal"] == _expected()["replay_seal"]
        assert after["replay_seal"] == _replay_seal(
            after["mesh_digest"],
            after["auth_stamp"],
            new_epoch,
            _hold_mesh(after["rows"]),
            _fold_mesh(after["rows"]),
        )
    finally:
        manifest.write_text(original, encoding="utf-8")
        _rebuild_and_run()


def test_k68_stamp_soft_poison() -> None:
    """A planted stamp.soft must not freeze auth_stamp rotate widths."""
    _rebuild_and_run()
    (SIDE / "stamp.soft").write_text("17", encoding="utf-8")
    _write_duty_cache([("hold:1", 3), ("train:1", 9)])
    (SIDE / "jrn").mkdir(parents=True, exist_ok=True)
    (SIDE / "jrn" / "seal.hint").write_text("13", encoding="utf-8")
    _rebuild_and_run()
    _assert_full_contract()
    assert _read_out()["auth_stamp"] == _expected()["auth_stamp"]


def test_k69_fold_mod3_shift_term() -> None:
    """Hold folds must include ((E mod 3) left-shift 24) beyond pad<<16."""
    manifest = MANIFEST
    original = manifest.read_text(encoding="utf-8")
    try:
        base = int(json.loads(original)["epoch"])
        epoch = base
        if epoch % 3 == 0:
            epoch = base + 1
            manifest.write_text(
                original.replace(f'"epoch": {base}', f'"epoch": {epoch}'),
                encoding="utf-8",
            )
        _rebuild_and_run()
        rows_in = {r["id"]: r for r in _load_rows()}
        for row in _read_out()["rows"]:
            if row["arm"] != "hold":
                continue
            meta = rows_in[row["row_id"]]
            h = int(row["hop_key"], 16)
            assert row["fold_tag"] == _exact(
                h, meta["pad"], 1, meta["lo"], meta["hi"], meta["w"], epoch
            )
            base_v = ((h & 0xFFFFFFFF) ^ (meta["lo"] * meta["w"])) & 0xFFFFFFFFFFFF
            without = (meta["pad"] * 0xA5A5) ^ (epoch & 0xFF) ^ (meta["pad"] << 16)
            prior = (
                _rotl64(base_v, _hold_rotate(meta["pad"], epoch))
                ^ meta["hi"]
                ^ without
            ) & 0xFFFFFFFFFFFF
            assert row["fold_tag"] != prior
    finally:
        manifest.write_text(original, encoding="utf-8")
        _rebuild_and_run()


def test_k70_main_hexemit_mesh_agreement() -> None:
    """Driver seal must agree with HexEmit mesh/stamp under the published seal formula."""
    _rebuild_and_run()
    got = _read_out()
    epoch = _epoch()
    assert got["replay_seal"] == _replay_seal(
        got["mesh_digest"],
        got["auth_stamp"],
        epoch,
        _hold_mesh(got["rows"]),
        _fold_mesh(got["rows"]),
    )
    (SIDE / "stamp.soft").write_text("5", encoding="utf-8")
    (SIDE / "mesh.pin").write_text("8", encoding="utf-8")
    _rebuild_and_run()
    got = _read_out()
    assert got["replay_seal"] == _expected()["replay_seal"]
    assert got["mesh_digest"] == _expected()["mesh_digest"]


def test_k71_walk_sum_not_product() -> None:
    """Hold walks must use (E plus pad), rejecting the prior (E times pad) false-green."""
    _rebuild_and_run()
    epoch = _epoch()
    seed = _bound_seed()
    found = False
    for r in _load_rows():
        if r["arm"] == 0:
            continue
        live = _hop_digest(r["pad"], seed, arm=1, epoch=epoch)
        product = _hop_digest(
            r["pad"],
            seed ^ _hold_walk_product_false_green(epoch, r["pad"]),
            arm=0,
            epoch=epoch,
        )
        if _hold_walk_mix(epoch, r["pad"]) != _hold_walk_product_false_green(
            epoch, r["pad"]
        ):
            assert live != product
            found = True
    assert found
    got = {r["row_id"]: r for r in _read_out()["rows"] if r["arm"] == "hold"}
    for r in _load_rows():
        if r["arm"] == 0:
            continue
        assert got[r["id"]]["hop_key"] == _hex16(
            _hop_digest(r["pad"], seed, arm=1, epoch=epoch)
        )
    manifest = MANIFEST
    original = manifest.read_text(encoding="utf-8")
    try:
        base = epoch
        new_epoch = base + 1
        while True:
            diverge = all(
                _hold_walk_mix(new_epoch, p)
                != _hold_walk_product_false_green(new_epoch, p)
                for p in (1, 2, 3, 4)
            )
            if (
                diverge
                and (new_epoch & 0xFF) != (base & 0xFF)
                and _hold_envelopes_ok_for_epoch(new_epoch)
            ):
                break
            new_epoch += 1
            if new_epoch > base + 500:
                raise AssertionError("no product-diverge epoch found")
        manifest.write_text(
            original.replace(f'"epoch": {base}', f'"epoch": {new_epoch}'),
            encoding="utf-8",
        )
        (SIDE / "hop.cache").write_text("seed=0\nbad=1\n", encoding="utf-8")
        (SIDE / "fold.soft").write_text("1", encoding="utf-8")
        (SIDE / "jrn").mkdir(parents=True, exist_ok=True)
        (SIDE / "jrn" / "epoch.snap").write_text(str(base), encoding="utf-8")
        _rebuild_and_run()
        after = {r["row_id"]: r for r in _read_out()["rows"] if r["arm"] == "hold"}
        for r in _load_rows():
            if r["arm"] == 0:
                continue
            live = _hop_digest(r["pad"], seed, arm=1, epoch=new_epoch)
            product = _hop_digest(
                r["pad"],
                seed ^ _hold_walk_product_false_green(new_epoch, r["pad"]),
                arm=0,
                epoch=new_epoch,
            )
            assert after[r["id"]]["hop_key"] == _hex16(live)
            assert after[r["id"]]["hop_key"] != _hex16(product)
        _assert_full_contract()
    finally:
        manifest.write_text(original, encoding="utf-8")
        _rebuild_and_run()


def _hold_envelopes_ok_for_epoch(epoch: int) -> bool:
    """Whether published hold spans stay inside the ibp envelope at epoch."""
    for r in _load_rows():
        if r["arm"] == 0:
            continue
        h = _hop_digest(r["pad"], arm=1, epoch=epoch)
        sp = _span(
            h, r["lo"], r["hi"], r["w"], arm=1, epoch=epoch, pad=r["pad"]
        )
        if not _envelope_ok("hold", sp):
            return False
    return True


def test_k72_coupled_stamp_soft_epoch_ladder() -> None:
    """stamp.soft plus epoch ladder must keep stamp, mesh, fold_mesh seal, and joins live."""
    manifest = MANIFEST
    original = manifest.read_text(encoding="utf-8")
    try:
        _rebuild_and_run()
        cur = _epoch()
        prev = _read_out()
        for step in range(1, 6):
            new_epoch = cur + step
            while True:
                if (
                    (new_epoch & 0xFF) != (cur & 0xFF)
                    and new_epoch % 3 != cur % 3
                    and new_epoch % 3 != 0
                    and new_epoch % 5 != cur % 5
                    and new_epoch % 7 != cur % 7
                    and all(
                        _hold_walk_mix(new_epoch, p)
                        != _hold_walk_product_false_green(new_epoch, p)
                        for p in (1, 2, 3, 4)
                    )
                    and _hold_envelopes_ok_for_epoch(new_epoch)
                ):
                    break
                new_epoch += 1
                if new_epoch > cur + 500:
                    raise AssertionError("no envelope-safe epoch found")
            text = manifest.read_text(encoding="utf-8")
            manifest.write_text(
                text.replace(f'"epoch": {cur}', f'"epoch": {new_epoch}'),
                encoding="utf-8",
            )
            (SIDE / "stamp.soft").write_text(str(3 + step), encoding="utf-8")
            _write_duty_cache(
                [
                    ("hold:1", step),
                    ("hold:3", 10 + step),
                    ("train:2", 20 + step),
                    ("train:4", 30 + step),
                ]
            )
            (SIDE / "fold.soft").write_text("1", encoding="utf-8")
            (SIDE / "span.soft").write_text("1", encoding="utf-8")
            (SIDE / "mesh.pin").write_text(str(50 + step), encoding="utf-8")
            _write_hop_cache(_bound_seed() ^ (step * 17), [("h07", step), ("t08", step)])
            (SIDE / "jrn").mkdir(parents=True, exist_ok=True)
            (SIDE / "jrn" / "epoch.snap").write_text(str(cur), encoding="utf-8")
            (SIDE / "jrn" / "seal.hint").write_text(str(40 + step), encoding="utf-8")
            _rebuild_and_run()
            _assert_full_contract()
            after = _read_out()
            assert after["auth_stamp"] != prev["auth_stamp"]
            assert after["replay_seal"] != prev["replay_seal"]
            assert after["mesh_digest"] != prev["mesh_digest"]
            hold_before = {
                r["row_id"]: (r["hop_key"], r["fold_tag"], r["span_u64"], r["join_hex"])
                for r in prev["rows"]
                if r["arm"] == "hold"
            }
            hold_after = {
                r["row_id"]: (r["hop_key"], r["fold_tag"], r["span_u64"], r["join_hex"])
                for r in after["rows"]
                if r["arm"] == "hold"
            }
            assert hold_after != hold_before
            prev = after
            cur = new_epoch
    finally:
        manifest.write_text(original, encoding="utf-8")
        _rebuild_and_run()
