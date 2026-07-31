import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/app/environment/tooling")
from digest_util import bank_fp_material, journal_duty_checksum, row_material_digest

ENV = Path("/app/environment")
BUNDLE_PATH = "/app/output/proof_certificate_bundle.tar.json"
BUNDLE = Path(BUNDLE_PATH)
TRACE_DIR = Path("/app/output/stage")
SCHEMA = ENV / "schemas/pcb_a763.schema.yaml"
SLICE_REF = ENV / "schemas/ref_a763.kaitai"


def _run_graded_cycle() -> None:
    if BUNDLE.exists():
        BUNDLE.unlink()
    for trace in TRACE_DIR.glob("lane_*.txt"):
        trace.unlink()
    bank = TRACE_DIR / "bank_cache.txt"
    if bank.exists():
        bank.unlink()
    subprocess.run(
        [str(ENV / "exec/run_hs_cycle.sh"), "--arm", "0763", "--all-fixtures"],
        check=True,
    )


def _load_certificate_doc() -> dict:
    return json.loads(BUNDLE.read_text(encoding="utf-8"))


def _cert_hex_ok(value: str) -> bool:
    if len(value) != 8:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return value == value.lower()


def _valid_ikey(value: str) -> bool:
    if not value.startswith("i") or len(value) != 5:
        return False
    try:
        int(value[1:], 16)
    except ValueError:
        return False
    return value[1:] == value[1:].lower()


def _run_replay_tool() -> None:
    subprocess.run(
        [str(ENV / "tooling/verify_ob9_d9.sh"), "--from", "/app/output/proof_certificate_bundle.tar.json"],
        check=True,
    )


def _run_g09_chk() -> None:
    subprocess.run([str(ENV / "o9_chk/g09_chk.sh"), BUNDLE_PATH, "9"], check=True)


def _kaitai_int(name: str) -> int:
    match = re.search(rf"^{name}:\s*(\d+)", SLICE_REF.read_text(encoding="utf-8"), re.MULTILINE)
    assert match, f"{name} missing from ref_a763.kaitai"
    return int(match.group(1))


def _tag_to_ikey(tag: int) -> str:
    base = _kaitai_int("reloc_base")
    stride = _kaitai_int("reloc_stride")
    bias = _kaitai_int("reloc_bias")
    xor_v = _kaitai_int("reloc_xor")
    if tag >= base:
        tag = ((tag - base) * stride + bias) ^ xor_v
    return f"i{tag:04x}"


def _kidx_duty_rows(path: Path) -> list[tuple[str, int]]:
    blob = path.read_bytes()
    assert blob[:4] == b"A763"
    count = int.from_bytes(blob[6:8], "little")
    offset = 8
    rows: list[tuple[str, int]] = []
    for _ in range(count):
        tag = int.from_bytes(blob[offset : offset + 4], "little")
        plen = int.from_bytes(blob[offset + 4 : offset + 8], "little")
        offset += 8
        payload = blob[offset : offset + plen]
        offset += plen
        duty = max(1, (sum(payload) + max(0, len(payload) - 1)) // max(1, len(payload)))
        rows.append((_tag_to_ikey(tag), duty))
    return rows


def _lane_journal_map(name: str) -> dict[str, str]:
    text = (TRACE_DIR / f"lane_{name}.txt").read_text(encoding="utf-8").strip()
    return dict(re.findall(r"([a-z_]+)=([^ ]+)", text))


def _lim_u32(name: str, default: int = 0) -> int:
    for line in (ENV / "k8m/lim_a763.toml").read_text(encoding="utf-8").splitlines():
        if line.startswith(name):
            raw = line.partition("=")[2].strip()
            if raw.lower().startswith("0x"):
                return int(raw, 16)
            return int(raw, 0)
    return default


def _od_margin(instance_key: str, corpus_tag: str, epoch: int) -> int:
    nibble = int(instance_key[1:], 16) & 0xFF
    tag_bit = 1 if corpus_tag == "a" else 0
    return ((nibble + _lim_u32("od_bias", 3)) * epoch + tag_bit) & 0xFF


def _row_digest(rows: list[dict], bank_fingerprint: str) -> str:
    return row_material_digest(rows, bank_fingerprint)


def _arm_profile_word() -> int:
    return _lim_u32("profile_word", 0x0763A7)


def _holdout_salt() -> int:
    return _lim_u32("holdout_salt", 0)


def _effective_cross(pair: dict, algebra: dict) -> int:
    mask = algebra.get("profile_mask", 0)
    return pair["cross_weight"] ^ (_arm_profile_word() & mask) ^ _holdout_salt()


def _additive_cross(pair: dict, algebra: dict) -> int:
    mask = algebra.get("profile_mask", 0)
    return pair["cross_weight"] + (_arm_profile_word() & mask)


def _corpus_duty_lookup(epoch: int) -> dict[tuple[str, str], int]:
    out: dict[tuple[str, str], int] = {}
    for path, tag in [
        (ENV / "k8m/corpus_a.kidx", "a"),
        (ENV / "k8m/corpus_b.kidx", "b"),
    ]:
        for key, duty in _kidx_duty_rows(path):
            out[(key, tag)] = duty + _od_margin(key, tag, epoch)
    return out


def _violation_slack() -> int:
    return _lim_u32("tolerance_band", 0)


def _lane_duty_tag(rows: list[dict]) -> str:
    return journal_duty_checksum(rows)


def _recomputed_catalog_nine(doc: dict) -> int:
    algebra = json.loads((ENV / "k8m/pair_v7.json").read_text(encoding="utf-8"))
    tolerance = _violation_slack()
    multiplier = max(1, int(algebra.get("stress_multiplier", 1)))
    rows = {(r["instance_key"], r["corpus_tag"]): r for r in doc.get("rows", [])}
    violations = 0
    for pair in algebra["instance_pairs"]:
        a = rows.get((pair["key_a"], "a"))
        b = rows.get((pair["key_b"], "b"))
        if a is None or b is None:
            violations += 1
            continue
        mc = _effective_cross(pair, algebra)
        scale = multiplier if int(a.get("lane_phase", 0)) >= 2 else 1
        duty_a = int(a["duty_cycles"])
        duty_b = int(b["duty_cycles"])
        if duty_b == 0 or duty_a % scale != 0:
            violations += 1
            continue
        raw_a = duty_a // scale
        derived_raw_a = max(0, raw_a - mc) // max(1, duty_b)
        expected = (derived_raw_a * duty_b + mc) * scale
        if abs(duty_a - expected) > tolerance:
            violations += 1
    return violations


def _expected_stress_duty_a(pair: dict, algebra: dict, bases: dict) -> int:
    mc = _effective_cross(pair, algebra)
    base_a = bases[(pair["key_a"], "a")]
    base_b = bases[(pair["key_b"], "b")]
    return (base_a * base_b + mc) * algebra["stress_multiplier"]


def _warm_base_rows() -> list[dict]:
    bases = _corpus_duty_lookup(_lim_u32("bank_epoch_warm", 1))
    rows = []
    for (key, tag), duty in bases.items():
        if tag == "a":
            rows.append({"instance_key": key, "corpus_tag": "a", "duty_cycles": duty})
    return rows


def _expected_bank_fingerprint() -> str:
    return bank_fp_material(
        _lim_u32("bank_epoch_stress", 2),
        _lim_u32("od_bias", 3),
        _arm_profile_word(),
    )


def test_hs_01_w3_stable():
    """Rows canonically ordered on stress lane with bank fingerprint bound."""
    _run_graded_cycle()
    doc = _load_certificate_doc()
    assert doc.get("rows")
    seq = [r["row_seq"] for r in doc["rows"]]
    assert seq == list(range(1, len(seq) + 1))
    assert [(r["instance_key"], r["corpus_tag"]) for r in doc["rows"]] == sorted(
        (r["instance_key"], r["corpus_tag"]) for r in doc["rows"]
    )
    assert {r["lane_phase"] for r in doc["rows"]} == {int(_lane_journal_map("stress")["lane"])}
    assert all(r["lane_phase"] >= 2 for r in doc["rows"])
    calib = _lane_journal_map("warm")
    scored = _lane_journal_map("stress")
    assert int(calib["rows"]) < int(scored["rows"])
    assert int(scored["rows"]) == len(doc["rows"])
    assert _cert_hex_ok(doc["bank_fingerprint"])
    assert doc["bank_fingerprint"] == _expected_bank_fingerprint()


def test_hs_02_replay_hash():
    """Independent replay digest must bind row material and bank fingerprint."""
    _run_graded_cycle()
    doc = _load_certificate_doc()
    digest = doc["replay_digest"]
    assert _cert_hex_ok(digest)
    assert digest == _row_digest(doc["rows"], doc["bank_fingerprint"])
    plain = row_material_digest(doc["rows"], "")
    assert digest != plain
    warm_status = _lane_journal_map("warm")["status"]
    assert _cert_hex_ok(warm_status)
    assert warm_status != digest
    assert _cert_hex_ok(_lane_journal_map("stress")["status"])
    assert warm_status != _lane_journal_map("stress")["status"]
    _run_replay_tool()
    _run_g09_chk()


def test_hs_03_row_totals():
    """Bundle rows must include stress-epoch stain margins before cross/stress fold."""
    _run_graded_cycle()
    doc = _load_certificate_doc()
    assert len(doc["rows"]) >= 2
    assert {r["corpus_tag"] for r in doc["rows"]} == {"a", "b"}
    assert all(r["duty_cycles"] > 0 for r in doc["rows"])
    algebra = json.loads((ENV / "k8m/pair_v7.json").read_text(encoding="utf-8"))
    stress_bases = _corpus_duty_lookup(_lim_u32("bank_epoch_stress", 2))
    warm_bases = _corpus_duty_lookup(_lim_u32("bank_epoch_warm", 1))
    for pair in algebra["instance_pairs"]:
        mc = _effective_cross(pair, algebra)
        assert mc != _additive_cross(pair, algebra)
        row_a = next(r for r in doc["rows"] if r["instance_key"] == pair["key_a"] and r["corpus_tag"] == "a")
        row_b = next(r for r in doc["rows"] if r["instance_key"] == pair["key_b"] and r["corpus_tag"] == "b")
        assert row_b["duty_cycles"] == stress_bases[(pair["key_b"], "b")]
        assert row_a["duty_cycles"] == _expected_stress_duty_a(pair, algebra, stress_bases)
        warm_expected = _expected_stress_duty_a(pair, algebra, warm_bases)
        assert row_a["duty_cycles"] != warm_expected
        assert row_a["duty_cycles"] >= mc
    scored = _lane_journal_map("stress")
    assert int(scored["rows"]) == len(doc["rows"])
    _run_replay_tool()
    _run_g09_chk()


def test_hs_04_kidx_keys():
    """Slice tags must decode with reloc_xor to the instance keys present in rows."""
    _run_graded_cycle()
    doc = _load_certificate_doc()
    expected = set()
    for fixture in sorted((ENV / "k8m").glob("corpus_*.kidx")):
        expected |= {key for key, _ in _kidx_duty_rows(fixture)}
    assert expected
    assert expected == {r["instance_key"] for r in doc["rows"]}
    assert len(doc["rows"]) == len(expected)
    bases = _corpus_duty_lookup(_lim_u32("bank_epoch_stress", 2))
    for row in doc["rows"]:
        assert row["lane_phase"] >= 2
        if row["corpus_tag"] == "b":
            assert row["duty_cycles"] == bases[(row["instance_key"], "b")]
    _run_g09_chk()


def test_hs_05_chain_integrity():
    """HS pipeline must publish a later scoring lane than the calibration pass."""
    _run_graded_cycle()
    doc = _load_certificate_doc()
    calib = _lane_journal_map("warm")
    scored = _lane_journal_map("stress")
    assert calib["lane"].isdigit()
    assert scored["lane"].isdigit()
    assert int(scored["witness_seq"]) > int(calib["witness_seq"])
    assert int(scored["lane"]) >= 2
    assert int(scored["rows"]) > int(calib["rows"])
    assert int(scored["rows"]) == len(doc["rows"])
    assert calib["pass"] == "warm"
    assert scored["pass"] == "stress"
    assert _cert_hex_ok(calib["status"])
    assert _cert_hex_ok(scored["status"])


def test_hs_06_arm_meta():
    """Arm 0763 metadata must appear in the regenerated bundle document."""
    _run_graded_cycle()
    doc = _load_certificate_doc()
    assert doc["arm_id"] == "0763"
    assert doc["obligation_violations"] == 0
    assert doc["bank_fingerprint"] == _expected_bank_fingerprint()
    assert doc["replay_digest"] == _row_digest(doc["rows"], doc["bank_fingerprint"])
    _run_replay_tool()
    _run_g09_chk()


def test_hs_07_tar_shape():
    """Bundle JSON shape and row hashes must be schema-complete."""
    _run_graded_cycle()
    doc = _load_certificate_doc()
    for row in doc["rows"]:
        assert _valid_ikey(row["instance_key"])
        assert row["corpus_tag"] in {"a", "b"}
    schema_text = SCHEMA.read_text(encoding="utf-8")
    assert "arm_id" in schema_text and "replay_digest" in schema_text
    assert "bank_fingerprint" in schema_text
    assert isinstance(doc["obligation_violations"], int)
    assert doc["obligation_violations"] == 0
    assert doc["replay_digest"] == _row_digest(doc["rows"], doc["bank_fingerprint"])
    seq = [r["row_seq"] for r in doc["rows"]]
    assert seq == list(range(1, len(seq) + 1))
    assert len(set(seq)) == len(seq)
    assert all(r["lane_phase"] >= 2 for r in doc["rows"])
    _run_replay_tool()
    _run_g09_chk()


def test_hs_08_catalog_nine():
    """Catalog item nine must match recomputed row algebra and pass replay."""
    _run_graded_cycle()
    doc = _load_certificate_doc()
    recomputed = _recomputed_catalog_nine(doc)
    assert doc["obligation_violations"] == recomputed
    assert recomputed == 0
    _run_replay_tool()

    saved = BUNDLE.read_text(encoding="utf-8")
    tampered = dict(doc)
    tampered["obligation_violations"] = recomputed + 1
    BUNDLE.write_text(json.dumps(tampered, indent=2) + "\n", encoding="utf-8")
    try:
        probe = subprocess.run(
            [str(ENV / "tooling/verify_ob9_d9.sh"), "--from", "/app/output/proof_certificate_bundle.tar.json"],
            text=True,
            check=False,
        )
        assert probe.returncode != 0
        g09 = subprocess.run(
            [str(ENV / "o9_chk/g09_chk.sh"), BUNDLE_PATH, "9"],
            text=True,
            check=False,
        )
        assert g09.returncode != 0
    finally:
        BUNDLE.write_text(saved, encoding="utf-8")


def test_hs_09_row_checksum():
    """Warm checksum binds margin-folded warm bases; stress binds post-fold rows."""
    _run_graded_cycle()
    doc = _load_certificate_doc()
    calib = _lane_journal_map("warm")
    scored = _lane_journal_map("stress")
    assert scored["duty_checksum"] == _lane_duty_tag(doc["rows"])
    assert _cert_hex_ok(scored["duty_checksum"])
    assert calib["duty_checksum"] == _lane_duty_tag(_warm_base_rows())
    assert calib["duty_checksum"] != scored["duty_checksum"]


def test_hs_10_stress_multiplier():
    """Stress-lane corpus a rows must reflect algebra stress_multiplier scaling."""
    _run_graded_cycle()
    doc = _load_certificate_doc()
    algebra = json.loads((ENV / "k8m/pair_v7.json").read_text(encoding="utf-8"))
    stress_multiplier = algebra["stress_multiplier"]
    assert stress_multiplier >= 2
    bases = _corpus_duty_lookup(_lim_u32("bank_epoch_stress", 2))
    for pair in algebra["instance_pairs"]:
        mc = _effective_cross(pair, algebra)
        row_a = next(r for r in doc["rows"] if r["instance_key"] == pair["key_a"] and r["corpus_tag"] == "a")
        row_b = next(r for r in doc["rows"] if r["instance_key"] == pair["key_b"] and r["corpus_tag"] == "b")
        duty_b = row_b["duty_cycles"]
        assert row_a["lane_phase"] >= 2
        assert row_a["duty_cycles"] >= (mc + duty_b) * stress_multiplier
        desk_wrong = bases[(pair["key_a"], "a")] * stress_multiplier * duty_b + mc
        assert row_a["duty_cycles"] != desk_wrong
    _run_g09_chk()


def test_hs_11_mask_blend():
    """Corpus a duties must use xor holdout-salted cross weights, not additive desk blend."""
    _run_graded_cycle()
    doc = _load_certificate_doc()
    algebra = json.loads((ENV / "k8m/pair_v7.json").read_text(encoding="utf-8"))
    bases = _corpus_duty_lookup(_lim_u32("bank_epoch_stress", 2))
    assert _holdout_salt() != 0
    for pair in algebra["instance_pairs"]:
        mc = _effective_cross(pair, algebra)
        additive = _additive_cross(pair, algebra)
        assert mc != additive
        expected = _expected_stress_duty_a(pair, algebra, bases)
        additive_expected = (bases[(pair["key_a"], "a")] * bases[(pair["key_b"], "b")] + additive) * algebra[
            "stress_multiplier"
        ]
        row_a = next(r for r in doc["rows"] if r["instance_key"] == pair["key_a"] and r["corpus_tag"] == "a")
        assert row_a["duty_cycles"] == expected
        assert row_a["duty_cycles"] != additive_expected
    _run_g09_chk()


def test_hs_12_bank_epoch_split():
    """Stress-epoch margins must diverge from warm-epoch margins for the same keys."""
    _run_graded_cycle()
    doc = _load_certificate_doc()
    warm_epoch = _lim_u32("bank_epoch_warm", 1)
    stress_epoch = _lim_u32("bank_epoch_stress", 2)
    assert stress_epoch != warm_epoch
    warm_fp = bank_fp_material(warm_epoch, _lim_u32("od_bias", 3), _arm_profile_word())
    assert doc["bank_fingerprint"] != warm_fp
    assert doc["bank_fingerprint"] == _expected_bank_fingerprint()
    for row in doc["rows"]:
        warm_m = _od_margin(row["instance_key"], row["corpus_tag"], warm_epoch)
        stress_m = _od_margin(row["instance_key"], row["corpus_tag"], stress_epoch)
        assert stress_m != warm_m
    algebra = json.loads((ENV / "k8m/pair_v7.json").read_text(encoding="utf-8"))
    stress_bases = _corpus_duty_lookup(stress_epoch)
    for pair in algebra["instance_pairs"]:
        row_a = next(r for r in doc["rows"] if r["instance_key"] == pair["key_a"] and r["corpus_tag"] == "a")
        assert row_a["duty_cycles"] == _expected_stress_duty_a(pair, algebra, stress_bases)
    _run_replay_tool()


def test_hs_13_recovery_rerun():
    """Back-to-back HS cycles must clear bank cache and stay deterministic."""
    _run_graded_cycle()
    first = _load_certificate_doc()
    bank = TRACE_DIR / "bank_cache.txt"
    assert bank.exists()
    bank.write_text("99\nstale=1\n", encoding="utf-8")
    _run_graded_cycle()
    second = _load_certificate_doc()
    assert second["replay_digest"] == first["replay_digest"]
    assert second["bank_fingerprint"] == first["bank_fingerprint"]
    assert second["bank_fingerprint"] == _expected_bank_fingerprint()
    for name in ("warm", "stress"):
        fields = _lane_journal_map(name)
        for key in ("pass", "lane", "witness_seq", "rows", "duty_checksum", "status"):
            assert key in fields
    _run_replay_tool()
    _run_g09_chk()
