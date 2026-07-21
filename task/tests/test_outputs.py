import json
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
ENV = APP / "environment"
BUILD = APP / "build"
OUT = APP / "output" / "forge_emit.json"
STATE = APP / "output" / "forge_checkpoint.json"
MANIFEST = ENV / "fixtures" / "lane.json"
BIN = BUILD / "forge_emit"
SEED = 1469598103934665603
STEP = 1099511628211
MASK = (1 << 64) - 1
UNITS_ALL = ["u_kappa", "u_alpha", "u_zeta"]
UNITS_ALL_CSV = ",".join(UNITS_ALL)
UNITS_RESUME = ["u_alpha", "u_zeta"]
UNITS_RESUME_CSV = ",".join(UNITS_RESUME)
BUILT = False


def _digest(text: str) -> str:
    h = SEED
    for b in text.encode():
        h ^= b
        h = (h * STEP) & MASK
    return f"{h:016x}"


def _unit_serial(unit: dict) -> str:
    return "|".join(
        [
            unit["name"],
            str(unit["manifest_bytes"]),
            str(unit["record_bytes"]),
            str(unit["drift_bytes"]),
            str(unit["order_rank"]),
            str(unit["order_weight"]),
        ]
    )


def _top_serial(doc: dict) -> str:
    parts = [
        f"{doc['schema_version']}|{doc['release_id']}|{doc['order_weight_base']}|"
        f"{doc['pass_epoch']}|{doc['total_drift_bytes']}|{doc['order_score']}"
    ]
    parts.extend(_unit_serial(unit) for unit in doc["units"])
    return "\n".join(parts)


def _build() -> None:
    global BUILT
    if BUILT:
        return
    subprocess.run(
        ["cmake", "-S", "/app/environment", "-B", "/app/build", "-G", "Ninja"],
        check=True,
        cwd=APP,
    )
    subprocess.run(["ninja", "-C", "/app/build"], check=True, cwd=APP)
    BUILT = True


@pytest.fixture(scope="session", autouse=True)
def _warm_build_once() -> None:
    _build()


def _manifest_meta() -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {
        "release_id": manifest["release_id"],
        "order_weight_base": manifest["order_weight_base"],
        "units": manifest["units"],
        "names": [entry["name"] for entry in manifest["units"]],
    }


def _read_record_bytes(record_path: Path) -> int:
    for line in record_path.read_text(encoding="utf-8").splitlines():
        if "size_bytes=" in line:
            return int(line.split("=", 1)[1].strip())
    return 0


def _descriptor_line(spec: dict) -> str:
    return "|".join(
        [
            spec["name"],
            spec["mode"],
            spec["record"],
            str(spec["manifest_bytes"]),
            str(spec["start_pass"]),
        ]
    )


def _expected_lane_token() -> str:
    meta = _manifest_meta()
    lines = sorted(_descriptor_line(spec) for spec in meta["units"])
    return _digest("\n".join(lines))


def _cold_weight(spec: dict, order_rank: int, base: int, record_bytes: int) -> int:
    return base * (order_rank + 1) + record_bytes


def _expected_unit(spec: dict, order_rank: int, base: int, checkpoint_entry: dict | None) -> dict:
    record_bytes = _read_record_bytes(ENV / "fixtures" / spec["record"])
    manifest_bytes = spec["manifest_bytes"]
    drift_bytes = record_bytes - manifest_bytes
    mode = spec["mode"]
    if checkpoint_entry is not None and mode == "resume":
        pass_index = checkpoint_entry["next_pass"]
        order_weight = checkpoint_entry["carry_weight"] + base + record_bytes
    else:
        pass_index = spec["start_pass"]
        order_weight = _cold_weight(spec, order_rank, base, record_bytes)
    return {
        "name": spec["name"],
        "mode": mode,
        "pass_index": pass_index,
        "manifest_bytes": manifest_bytes,
        "record_bytes": record_bytes,
        "drift_bytes": drift_bytes,
        "order_rank": order_rank,
        "order_weight": order_weight,
    }


def _run(units_csv: str, *, keep_state: bool = False) -> tuple[dict, bytes]:
    _build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    if not keep_state and STATE.exists():
        STATE.unlink()
    subprocess.run(
        [
            str(BIN),
            str(MANIFEST),
            str(OUT),
            units_csv,
        ],
        check=True,
        cwd=APP,
    )
    raw = OUT.read_bytes()
    return json.loads(raw), raw


def _run_with_state(units_csv: str) -> tuple[dict, dict]:
    _build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    subprocess.run(
        [
            str(BIN),
            str(MANIFEST),
            str(OUT),
            units_csv,
        ],
        check=True,
        cwd=APP,
    )
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    state = json.loads(STATE.read_text(encoding="utf-8"))
    return doc, state


def _by_name(doc: dict, name: str) -> dict:
    for unit in doc["units"]:
        if unit["name"] == name:
            return unit
    raise AssertionError(f"missing unit for {name}")


def _state_map(state: dict) -> dict[str, dict]:
    assert set(state) >= {"schema_version", "lane_token", "pass_epoch", "units"}
    assert state["schema_version"] == 1
    assert len(state["lane_token"]) == 16
    assert state["lane_token"] == _expected_lane_token()
    names = [entry["name"] for entry in state["units"]]
    assert names == sorted(names)
    mapping = {}
    for entry in state["units"]:
        assert set(entry) == {"name", "next_pass", "carry_weight", "carry_drift"}
        assert entry["name"] in UNITS_RESUME
        mapping[entry["name"]] = entry
    return mapping


def _write_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, separators=(",", ":")) + "\n")


def _assert_schema(doc: dict, requested: list[str]) -> None:
    meta = _manifest_meta()
    assert doc["schema_version"] == 1
    assert doc["release_id"] == meta["release_id"]
    assert doc["order_weight_base"] == meta["order_weight_base"]
    assert isinstance(doc["pass_epoch"], int)
    assert len(doc["digest"]) == 16
    assert doc["digest"] == _digest(_top_serial(doc))
    assert [unit["name"] for unit in doc["units"]] == requested
    drift_total = 0
    weight_total = 0
    for unit in doc["units"]:
        assert set(unit) == {
            "name",
            "mode",
            "pass_index",
            "manifest_bytes",
            "record_bytes",
            "drift_bytes",
            "order_rank",
            "order_weight",
            "row_digest",
        }
        assert unit["row_digest"] == _digest(_unit_serial(unit))
        drift_total += abs(unit["drift_bytes"])
        weight_total += unit["order_weight"]
    assert doc["total_drift_bytes"] == drift_total
    assert doc["order_score"] == weight_total


def _assert_carry(entry: dict, unit: dict) -> None:
    assert entry["next_pass"] == unit["pass_index"] + 1
    assert entry["carry_weight"] == unit["order_weight"]
    assert entry["carry_drift"] == unit["drift_bytes"]


def test_q0_cold_lane_baseline():
    """Cold unit u_kappa reports parsed record bytes, zero drift, and cold weight formula."""
    doc, _ = _run("u_kappa")
    _assert_schema(doc, ["u_kappa"])
    meta = _manifest_meta()
    spec = meta["units"][0]
    unit = _by_name(doc, "u_kappa")
    expected = _expected_unit(spec, 0, doc["order_weight_base"], None)
    assert unit["mode"] == "cold"
    for key, value in expected.items():
        assert unit[key] == value


def test_q1_corrupt_checkpoint_fresh_start():
    """Corrupt lane checkpoint is ignored and resume units restart at configured start_pass."""
    seed_doc, seed_state = _run_with_state(UNITS_RESUME_CSV)
    _assert_schema(seed_doc, UNITS_RESUME)
    token = seed_state["lane_token"]
    _write_state(
        {
            "schema_version": 1,
            "lane_token": token[::-1],
            "pass_epoch": 0,
            "units": [{"name": "u_alpha", "next_pass": 99, "carry_weight": 1, "carry_drift": 0}],
        }
    )
    doc, state = _run_with_state(UNITS_RESUME_CSV)
    _assert_schema(doc, UNITS_RESUME)
    alpha = _by_name(doc, "u_alpha")
    zeta = _by_name(doc, "u_zeta")
    meta = _manifest_meta()
    assert alpha["pass_index"] == meta["units"][1]["start_pass"]
    assert zeta["pass_index"] == meta["units"][2]["start_pass"]
    saved = _state_map(state)
    _assert_carry(saved["u_alpha"], alpha)
    _assert_carry(saved["u_zeta"], zeta)


def test_q2_stale_lane_token_rejected():
    """Well-formed but stale lane tokens do not seed resume carry fields."""
    doc, state = _run_with_state("u_alpha")
    run = _by_name(doc, "u_alpha")
    saved = _state_map(state)
    _assert_carry(saved["u_alpha"], run)
    stale = {
        "schema_version": 1,
        "lane_token": state["lane_token"][::-1],
        "pass_epoch": saved["u_alpha"]["next_pass"],
        "units": [
            {
                "name": "u_alpha",
                "next_pass": saved["u_alpha"]["next_pass"] + 5,
                "carry_weight": saved["u_alpha"]["carry_weight"] + 1000,
                "carry_drift": 0,
            }
        ],
    }
    _write_state(stale)
    replay_doc, _ = _run_with_state("u_alpha")
    replay = _by_name(replay_doc, "u_alpha")
    meta = _manifest_meta()
    assert replay["pass_index"] == meta["units"][1]["start_pass"]


def test_q3_resume_carry_weight_chain():
    """Chained resume invocations advance pass_index and accumulate carry_weight."""
    if OUT.exists():
        OUT.unlink()
    if STATE.exists():
        STATE.unlink()
    first_doc, first_state = _run_with_state("u_zeta")
    first = _by_name(first_doc, "u_zeta")
    first_map = _state_map(first_state)
    _assert_carry(first_map["u_zeta"], first)

    second_doc, second_state = _run_with_state("u_zeta")
    second = _by_name(second_doc, "u_zeta")
    assert second["pass_index"] == first_map["u_zeta"]["next_pass"]
    meta = _manifest_meta()
    expected = _expected_unit(meta["units"][2], 2, second_doc["order_weight_base"], first_map["u_zeta"])
    assert second["order_weight"] == expected["order_weight"]
    second_map = _state_map(second_state)
    _assert_carry(second_map["u_zeta"], second)


def test_q4_subset_preserves_other_checkpoints():
    """Partial resume requests preserve checkpoints for omitted resume units."""
    if OUT.exists():
        OUT.unlink()
    if STATE.exists():
        STATE.unlink()
    full_doc, full_state = _run_with_state(UNITS_RESUME_CSV)
    full_alpha = _by_name(full_doc, "u_alpha")
    full_zeta = _by_name(full_doc, "u_zeta")
    full_map = _state_map(full_state)
    _assert_carry(full_map["u_alpha"], full_alpha)
    _assert_carry(full_map["u_zeta"], full_zeta)

    partial_doc, partial_state = _run_with_state("u_alpha")
    partial_alpha = _by_name(partial_doc, "u_alpha")
    partial_map = _state_map(partial_state)
    assert partial_alpha["pass_index"] == full_map["u_alpha"]["next_pass"]
    assert partial_map["u_zeta"]["next_pass"] == full_map["u_zeta"]["next_pass"]
    assert partial_map["u_zeta"]["carry_weight"] == full_map["u_zeta"]["carry_weight"]


def test_q5_lane_replay_determinism():
    """Two cold-only invocations with cleared checkpoint state match byte-for-byte."""
    first_doc, first_raw = _run("u_kappa")
    second_doc, second_raw = _run("u_kappa")
    assert first_raw == second_raw
    assert first_doc["digest"] == second_doc["digest"]


def test_q6_mixed_lane_totals():
    """Full lane request keeps absolute drift totals and manifest-order rank weights."""
    doc, _ = _run(UNITS_ALL_CSV)
    _assert_schema(doc, UNITS_ALL)
    meta = _manifest_meta()
    for idx, spec in enumerate(meta["units"]):
        unit = _by_name(doc, spec["name"])
        expected = _expected_unit(spec, idx, doc["order_weight_base"], None)
        for key in ("manifest_bytes", "record_bytes", "drift_bytes", "order_rank", "order_weight"):
            assert unit[key] == expected[key]
    assert doc["total_drift_bytes"] == sum(abs(unit["drift_bytes"]) for unit in doc["units"])


def test_q7_cold_ignores_advanced_checkpoint():
    """Cold u_kappa always recomputes from start_pass even when resume checkpoints are advanced."""
    if OUT.exists():
        OUT.unlink()
    if STATE.exists():
        STATE.unlink()
    for _ in range(2):
        _run_with_state(UNITS_RESUME_CSV)
    doc, _ = _run_with_state("u_kappa")
    _assert_schema(doc, ["u_kappa"])
    cold = _by_name(doc, "u_kappa")
    meta = _manifest_meta()
    expected = _expected_unit(meta["units"][0], 0, doc["order_weight_base"], None)
    assert cold["mode"] == "cold"
    assert cold["pass_index"] == expected["pass_index"]
    assert cold["order_weight"] == expected["order_weight"]


def test_q8_resume_digest_differs_with_flat_drift():
    """Second resume emission changes digest while per-unit drift stays zero on bundled records."""
    if OUT.exists():
        OUT.unlink()
    if STATE.exists():
        STATE.unlink()
    first_doc, _ = _run_with_state("u_zeta")
    first = _by_name(first_doc, "u_zeta")
    assert first["record_bytes"] == first["manifest_bytes"]
    second_doc, _ = _run_with_state("u_zeta")
    second = _by_name(second_doc, "u_zeta")
    assert second["record_bytes"] == second["manifest_bytes"]
    assert first_doc["digest"] != second_doc["digest"]
    assert first["row_digest"] != second["row_digest"]


def test_q9_triple_resume_chain():
    """Three chained u_zeta invocations keep pass_index cadence aligned with stored next_pass."""
    if OUT.exists():
        OUT.unlink()
    if STATE.exists():
        STATE.unlink()
    prior = None
    for _ in range(3):
        doc, state = _run_with_state("u_zeta")
        run = _by_name(doc, "u_zeta")
        assert run["record_bytes"] == run["manifest_bytes"]
        state_map = _state_map(state)
        if prior is not None:
            assert run["pass_index"] == prior["u_zeta"]["next_pass"]
        _assert_carry(state_map["u_zeta"], run)
        prior = state_map


def test_q10_lane_token_matches_descriptor():
    """Lane token matches digest over sorted manifest unit descriptors."""
    _, state = _run_with_state(UNITS_RESUME_CSV)
    assert state["lane_token"] == _expected_lane_token()
