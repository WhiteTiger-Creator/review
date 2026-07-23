"""Behavioral checks for the advocacy label-shift desk outputs."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

import pytest

PACK = Path("/app/data/board_q3")
ALT_PACK = Path("/app/data/board_alt")
OUT = Path("/app/output")
SCORE = OUT / "scenario_score.json"
BRIEF = OUT / "uncertainty_brief.md"
LEDGER = OUT / "desk_ledger.json"
TAPE = OUT / "stage_tape.jsonl"
DESK = "/app/environment/scripts/run_desk.sh"


def _execute_discharge_risk_pipeline(pack: str = "/app/data/board_q3", out: str = "/app/output") -> None:
    subprocess.run(
        [DESK, "--pack", pack, "--out", out],
        check=True,
        cwd="/app",
    )


def _read_scenario_score_json(path: Path = SCORE) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _format_to_six_decimals(n: float) -> str:
    return f"{float(n):.6f}"


def _calculate_sha256_hash(parts: list[object]) -> str:
    line = "|".join(str(p) for p in parts)
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def _compute_pack_manifest_digest(manifest: dict) -> str:
    return _calculate_sha256_hash(
        [
            manifest["ckpt"],
            int(manifest["seed"]),
            int(manifest["nSalt"]),
            int(manifest["kParts"]),
            int(manifest["xSlot"]),
            int(manifest["span"]),
        ]
    )


def _compute_expected_stage_seals(score: dict, brief: str, n_salt: int) -> dict[str, str]:
    table = score["scoring_table"]
    return {
        "cal": _calculate_sha256_hash(
            [
                "cal",
                int(score["train_end_slot"]),
                int(score["eval_start_slot"]),
                int(score["temporal_leak_probe"]),
            ]
        ),
        "prio": _calculate_sha256_hash(
            ["prio", _format_to_six_decimals(score["prior_delta"]), _format_to_six_decimals(score["prior_delta_residual"])]
        ),
        "gauge": _calculate_sha256_hash(
            [
                "gauge",
                _format_to_six_decimals(score["acc_home"]),
                _format_to_six_decimals(score["acc_shift"]),
                _format_to_six_decimals(score["acc_gap"]),
                int(n_salt),
            ]
        ),
        "brief": _calculate_sha256_hash(["brief", len(brief), len(table)]),
    }


def _compute_reproducibility_digest(score: dict, n_salt: int) -> str:
    return _calculate_sha256_hash(
        [
            int(score["seed"]),
            int(score["train_end_slot"]),
            int(score["eval_start_slot"]),
            int(score["temporal_leak_probe"]),
            _format_to_six_decimals(score["prior_delta"]),
            _format_to_six_decimals(score["prior_delta_residual"]),
            _format_to_six_decimals(score["acc_home"]),
            _format_to_six_decimals(score["acc_shift"]),
            _format_to_six_decimals(score["acc_gap"]),
            int(n_salt),
            score["pack_digest"],
            score["ledger_chain"],
        ]
    )


def _parse_brief_table_rows(text: str) -> dict[str, str]:
    vals: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) < 2:
            continue
        key, val = parts[0], parts[1]
        if key in {"question", "---"} or set(key) <= {"-"}:
            continue
        vals[key] = val
    return vals


def _parse_stage_tape_events(path: Path = TAPE) -> list[dict]:
    if not path.exists():
        return []
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


@pytest.fixture(scope="module")
def desk_once() -> dict:
    _execute_discharge_risk_pipeline()
    return _read_scenario_score_json()


def test_brief_table_and_fences(desk_once: dict) -> None:
    """Artifacts exist; brief floats match scoring_table; no fences; tape has 4 lines."""
    assert SCORE.exists()
    assert BRIEF.exists()
    assert LEDGER.exists()
    assert TAPE.exists()
    score = desk_once
    assert int(score["tape_seal_count"]) == 4
    brief = BRIEF.read_text(encoding="utf-8")
    assert "```" not in brief
    table = score["scoring_table"]
    brief_map = _parse_brief_table_rows(brief)
    float_keys = {
        "prior_delta",
        "prior_delta_residual",
        "acc_home",
        "acc_shift",
        "acc_gap",
    }
    assert len(score) > 0
    assert "partition_policy" in score
    assert "temporal_leak_probe" in score
    assert "acc_gap" in score
    assert isinstance(score["acc_gap"], (int, float))
    assert isinstance(score["prior_delta"], (int, float))
    assert isinstance(score["acc_home"], (int, float))
    assert isinstance(score["acc_shift"], (int, float))
    assert isinstance(score["prior_delta_residual"], (int, float))
    assert isinstance(score["temporal_leak_probe"], (int, float))
    assert isinstance(score["train_end_slot"], (int, float))
    assert isinstance(score["eval_start_slot"], (int, float))
    assert isinstance(score["seed"], (int, float))
    assert isinstance(score["tape_seal_count"], (int, float))
    assert isinstance(score["checkpoint_stamp"], str)
    assert isinstance(score["pack_digest"], str)
    assert isinstance(score["ledger_chain"], str)
    assert isinstance(score["resume_stamp"], str)
    assert isinstance(score["repro_digest"], str)
    assert isinstance(score["partition_policy"], str)
    assert isinstance(score["scoring_table"], dict)
    assert isinstance(score["stage_seals"], dict)
    assert isinstance(score["held_out"], dict)
    assert len(score["checkpoint_stamp"]) > 0
    assert len(score["pack_digest"]) > 0
    assert len(score["ledger_chain"]) > 0
    assert len(score["resume_stamp"]) > 0
    assert len(score["repro_digest"]) > 0
    assert len(score["partition_policy"]) > 0
    for key, raw in table.items():
        assert key in brief_map
        if key in float_keys:
            assert brief_map[key] == _format_to_six_decimals(float(raw))
        else:
            assert brief_map[key] == str(int(raw))
    ordered_keys = sorted(table.keys(), key=lambda k: (len(k), k))
    brief_keys = [k for k in brief_map.keys() if k in table]
    assert brief_keys == ordered_keys, "Brief rows not length-then-alpha"
    tape = _parse_stage_tape_events()
    assert len(tape) == 4
    tags = [ev["tag"] for ev in tape]
    assert tags == ["cal", "prio", "gauge", "brief"]
    assert all(isinstance(ev["tag"], str) for ev in tape)
    assert all(len(ev["tag"]) > 0 for ev in tape)


def test_overwrite_trap_regeneration() -> None:
    """Overwrite trap regenerates score, brief, ledger, and tape."""
    from os import makedirs

    makedirs(str(OUT), exist_ok=True)
    SCORE.write_text("{}\n", encoding="utf-8")
    fence = chr(96) * 3
    BRIEF.write_text(fence + "\nx\n" + fence + "\n", encoding="utf-8")
    LEDGER.write_text("{}\n", encoding="utf-8")
    TAPE.write_text('{"tag":"stale"}\n', encoding="utf-8")
    _execute_discharge_risk_pipeline()
    score = _read_scenario_score_json()
    assert "prior_delta" in score
    assert score.get("pack_digest")
    assert score.get("ledger_chain")
    assert int(score["tape_seal_count"]) == 4
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert ledger["ledger_chain"] == score["ledger_chain"]
    assert ledger["pack_digest"] == score["pack_digest"]
    brief = BRIEF.read_text(encoding="utf-8")
    assert fence not in brief
    tape = _parse_stage_tape_events()
    assert len(tape) == 4
    assert all(ev.get("pack_digest") == score["pack_digest"] for ev in tape)
    assert isinstance(ledger["stage_seals"], dict)
    assert len(ledger["stage_seals"]) == 4
    assert "cal" in ledger["stage_seals"]
    assert "prio" in ledger["stage_seals"]
    assert "gauge" in ledger["stage_seals"]
    assert "brief" in ledger["stage_seals"]


def test_temporal_leak_split(desk_once: dict) -> None:
    """Temporal leak probe clean with positive calendar gap."""
    score = desk_once
    assert int(score["temporal_leak_probe"]) == 0
    assert int(score["train_end_slot"]) < int(score["eval_start_slot"])
    assert isinstance(score["train_end_slot"], int)
    assert isinstance(score["eval_start_slot"], int)


def test_prior_shift_and_residuals(desk_once: dict) -> None:
    """Primary prior shift surfaces and residual survives covariates."""
    score = desk_once
    assert float(score["prior_delta"]) >= 0.12
    assert float(score["prior_delta_residual"]) >= 0.08
    assert isinstance(score["prior_delta"], (int, float))
    assert isinstance(score["prior_delta_residual"], (int, float))


def test_held_out_rejection(desk_once: dict) -> None:
    """Held-out corpus rejects covariate burial; differs from primary."""
    score = desk_once
    held = score["held_out"]
    assert float(held["prior_delta"]) >= 0.12
    assert float(held["prior_delta_residual"]) >= 0.08
    assert int(held["temporal_leak_probe"]) == 0
    assert float(held["prior_delta"]) != float(score["prior_delta"])
    assert isinstance(held, dict)
    assert "prior_delta" in held


def test_accuracy_gap_perturbed(desk_once: dict) -> None:
    """Accuracy gap remains when prior shift is present."""
    score = desk_once
    assert float(score["prior_delta"]) >= 0.12
    assert float(score["acc_gap"]) >= 0.05
    assert float(score["acc_home"]) > float(score["acc_shift"])
    assert isinstance(score["acc_home"], (int, float))
    assert isinstance(score["acc_shift"], (int, float))


def test_ledger_integrity_and_seals(desk_once: dict) -> None:
    """Pack digest, stage seals, ledger chain, resume stamp, and repro digest."""
    score = desk_once
    brief = BRIEF.read_text(encoding="utf-8")
    manifest = json.loads((PACK / "manifest.json").read_text(encoding="utf-8"))
    n_salt = int(manifest["nSalt"])
    assert score["checkpoint_stamp"] == manifest["ckpt"]
    assert score["pack_digest"] == _compute_pack_manifest_digest(manifest)
    assert int(score["tape_seal_count"]) == 4
    seals = _compute_expected_stage_seals(score, brief, n_salt)
    assert score["stage_seals"] == seals
    expected_chain = _calculate_sha256_hash(
        [score["pack_digest"], seals["cal"], seals["prio"], seals["gauge"], seals["brief"]]
    )
    assert score["ledger_chain"] == expected_chain
    assert score["resume_stamp"] == _calculate_sha256_hash([score["ledger_chain"], 4])
    assert score["repro_digest"] == _compute_reproducibility_digest(score, n_salt)
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert ledger["ledger_chain"] == score["ledger_chain"]
    assert ledger["resume_stamp"] == score["resume_stamp"]
    assert ledger["stage_seals"] == seals
    tape = _parse_stage_tape_events()
    for tag, seal in seals.items():
        ev = next(e for e in tape if e["tag"] == tag)
        assert ev["seal"] == seal
        assert ev["pack_digest"] == score["pack_digest"]
    assert len(score["pack_digest"]) == 64
    assert len(score["ledger_chain"]) == 64
    assert len(score["resume_stamp"]) == 64
    assert len(score["repro_digest"]) == 64


def test_consecutive_byte_identity() -> None:
    """Consecutive identical runs emit byte-identical score and ledger."""
    _execute_discharge_risk_pipeline()
    first = SCORE.read_bytes()
    first_ledger = LEDGER.read_bytes()
    _execute_discharge_risk_pipeline()
    second = SCORE.read_bytes()
    second_ledger = LEDGER.read_bytes()
    assert first == second
    assert first_ledger == second_ledger
    score = json.loads(first.decode("utf-8"))
    assert score["partition_policy"] == "strict_calendar_gap"
    assert int(score["seed"]) == 42
    brief = BRIEF.read_text(encoding="utf-8")
    assert "```" not in brief
    assert re.search(r"\|", brief) is not None
    if float(score["prior_delta"]) >= 0.12 and float(score["prior_delta_residual"]) >= 0.08:
        assert float(score["acc_gap"]) >= 0.05
    assert isinstance(score["stage_seals"], dict)
    assert len(score["stage_seals"]) == 4


def test_journal_tape_recovery() -> None:
    """Journal recovery restores ledger from stage tape when checkpoint is gone."""
    _execute_discharge_risk_pipeline()
    score = _read_scenario_score_json()
    ckpt = score["checkpoint_stamp"]
    ckpt_file = OUT / "checkpoints" / f"{ckpt}.json"
    assert ckpt_file.exists()
    assert TAPE.exists()

    original_chain = score["ledger_chain"]
    ledger_data = json.loads(LEDGER.read_text(encoding="utf-8"))
    ledger_data["ledger_chain"] = "corrupt_chain_value_12345"
    LEDGER.write_text(json.dumps(ledger_data, indent=2) + "\n", encoding="utf-8")
    ckpt_file.unlink()

    _execute_discharge_risk_pipeline()

    restored_ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert restored_ledger["ledger_chain"] == original_chain
    assert restored_ledger["ledger_chain"] == score["ledger_chain"]
    tape = _parse_stage_tape_events()
    assert len(tape) == 4
    assert all(ev.get("pack_digest") == score["pack_digest"] for ev in tape)
    assert isinstance(restored_ledger["stage_seals"], dict)
    assert len(restored_ledger["stage_seals"]) == 4


def test_journal_tape_replay_fails_on_bad_digest() -> None:
    """Corrupt ledger + missing checkpoint + wrong tape digest must not silently heal."""
    _execute_discharge_risk_pipeline()
    score = _read_scenario_score_json()
    ckpt = score["checkpoint_stamp"]
    ckpt_file = OUT / "checkpoints" / f"{ckpt}.json"
    assert ckpt_file.exists()
    assert TAPE.exists()

    corrupt_chain = "corrupt_chain_value_12345"
    ledger_data = json.loads(LEDGER.read_text(encoding="utf-8"))
    ledger_data["ledger_chain"] = corrupt_chain
    LEDGER.write_text(json.dumps(ledger_data, indent=2) + "\n", encoding="utf-8")
    ckpt_file.unlink()

    bad_events = []
    for line in TAPE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        ev = json.loads(line)
        ev["pack_digest"] = "0" * 64
        bad_events.append(ev)
    TAPE.write_text("\n".join(json.dumps(ev) for ev in bad_events) + "\n", encoding="utf-8")

    _execute_discharge_risk_pipeline()

    unrecovered = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert unrecovered["ledger_chain"] == corrupt_chain
    assert unrecovered["ledger_chain"] != score["ledger_chain"]


def test_margin_perturbation_controlled() -> None:
    """Margin tie-break perturbation yields accShift 0.25 for controlled logits."""
    code = """
    const { setTrueBuf } = require('/app/dist/c5/g2/gauge_types');
    const { vGauge } = require('/app/dist/c5/g2/v_gauge');
    setTrueBuf([0.1, -0.1, 0.5, -0.5]);
    const res = vGauge([1.0, 1.0, 1.0, 1.0], [1.0, 1.0, 1.0, 1.0], 1);
    console.log(res.accShift);
    """
    res = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True)
    acc_shift = float(res.stdout.strip())
    assert acc_shift == 0.25
    assert res.returncode == 0
    assert len(res.stdout) > 0


def test_alternate_pack_handling() -> None:
    """Alternate pack yields distinct digest, prior, and valid ledger with K=2 gap."""
    alt_manifest = json.loads((ALT_PACK / "manifest.json").read_text(encoding="utf-8"))
    assert int(alt_manifest["nSalt"]) == 5

    with tempfile.TemporaryDirectory(prefix="board_alt_") as tmp:
        alt_out = Path(tmp)
        _execute_discharge_risk_pipeline(pack=str(ALT_PACK), out=str(alt_out))
        alt_score = _read_scenario_score_json(alt_out / "scenario_score.json")
        primary_score = _read_scenario_score_json()

        assert alt_score["pack_digest"] != primary_score["pack_digest"]
        assert alt_score["pack_digest"] == _compute_pack_manifest_digest(alt_manifest)
        assert float(alt_score["prior_delta"]) != float(primary_score["prior_delta"])
        assert float(alt_score["prior_delta"]) >= 0.12

        brief = (alt_out / "uncertainty_brief.md").read_text(encoding="utf-8")
        seals = _compute_expected_stage_seals(alt_score, brief, int(alt_manifest["nSalt"]))
        expected_chain = _calculate_sha256_hash(
            [
                alt_score["pack_digest"],
                seals["cal"],
                seals["prio"],
                seals["gauge"],
                seals["brief"],
            ]
        )
        assert alt_score["ledger_chain"] == expected_chain
        assert float(alt_score["acc_gap"]) >= 0.05
        assert float(alt_score["acc_home"]) > float(alt_score["acc_shift"])
        assert isinstance(alt_score, dict)
        assert "ledger_chain" in alt_score
        assert "resume_stamp" in alt_score


def test_stage_tape_event_order(desk_once: dict) -> None:
    """Primary run tape lines share pack digest and cal/prio/gauge/brief order."""
    score = desk_once
    tape = _parse_stage_tape_events()
    assert len(tape) == 4
    digest = score["pack_digest"]
    for ev in tape:
        assert ev["pack_digest"] == digest
    assert [ev["tag"] for ev in tape] == ["cal", "prio", "gauge", "brief"]
    assert len(digest) == 64
    assert isinstance(digest, str)

