"""Observation verification for journaled prioritized-replay migration skew."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

APP = Path("/app")
OUT = APP / "output"
OBS = OUT / "training_observations.json"
AUDIT = OUT / "halt_audit.json"
REPLAY = OUT / "replay_audit.json"
BIN = APP / "bin" / "lanectl"
MATRIX = APP / "environment" / "scripts" / "run_matrix.sh"
CONFIG = APP / "environment" / "configs" / "train.toml"
PACK = APP / "environment" / "data" / "pack_rows.json"

SEED = 77103
EVAL_BAND = 0.05
TWIN_SKEW_MAX = 0.12
TWIN_CEILING_MIN = 0.85


def _run_cmd(command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(command, check=False, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return proc


def _run_matrix(case_id: str, state_root: Path) -> dict[str, Any]:
    env = {
        **dict(os.environ),
        "LANE_STATE_ROOT": str(state_root),
        "LANE_OUT": str(OBS),
    }
    if OBS.exists():
        OBS.unlink()
    _run_cmd(["bash", str(MATRIX), case_id], env=env)
    payload = json.loads(OBS.read_text(encoding="utf-8"))
    assert payload["seed"] == SEED
    assert payload["runs"], "expected at least one run record"
    return next(r for r in payload["runs"] if r["scenario"] == case_id)


def _rel_band(held: float, base: float) -> float:
    return abs(held - base) / max(abs(base), 1e-12)


def _ceilings_commensurate(mig: dict[str, Any], reb: dict[str, Any], rel: float = 0.05) -> bool:
    mig_draws = mig["draws"]
    reb_draws = reb["draws"]
    left = float(mig_draws[len(mig_draws) - 1]["ceiling"])
    right = float(reb_draws[len(reb_draws) - 1]["ceiling"])
    gap = abs(left - right)
    limit = max(1e-6, rel * abs(right))
    return gap <= limit


def _final_era_matches_live(run: dict[str, Any], audit: dict[str, Any]) -> bool:
    draws = run["draws"]
    idx = len(draws) - 1
    final_era = int(draws[idx]["era"])
    live = int(audit["live_gen"])
    return final_era == live


def _post_bump_ceilings_stable(draws: list[dict[str, Any]], rel: float = 0.05) -> bool:
    post = [d for d in draws if int(d["ordinal"]) >= 6]
    if len(post) < 3:
        return False
    final_ceil = float(draws[len(draws) - 1]["ceiling"])
    for d in post[len(post) - 3 :]:
        gap = abs(float(d["ceiling"]) - final_ceil)
        if gap > max(1e-6, rel * abs(final_ceil)):
            return False
    return True


def _last_step_ordinal(run: dict[str, Any]) -> int:
    steps = run["steps"]
    if not steps:
        return -1
    return int(steps[len(steps) - 1]["ordinal"])


def _inspect(state: Path) -> dict[str, Any]:
    env = {**dict(os.environ), "LANE_STATE_ROOT": str(state)}
    if AUDIT.exists():
        AUDIT.unlink()
    _run_cmd(
        [
            str(BIN),
            "inspect",
            "--config",
            str(CONFIG),
            "--pack",
            str(PACK),
            "--state",
            str(state),
            "--out",
            str(AUDIT),
        ],
        env=env,
    )
    return json.loads(AUDIT.read_text(encoding="utf-8"))


def _replay(state: Path, scenario: str) -> dict[str, Any]:
    env = {**dict(os.environ), "LANE_STATE_ROOT": str(state)}
    if REPLAY.exists():
        REPLAY.unlink()
    _run_cmd(
        [
            str(BIN),
            "replay",
            "--config",
            str(CONFIG),
            "--pack",
            str(PACK),
            "--state",
            str(state),
            "--out",
            str(REPLAY),
            "--scenario",
            scenario,
        ],
        env=env,
    )
    return json.loads(REPLAY.read_text(encoding="utf-8"))


def test_migrate_rebuild_parity() -> None:
    """Migrate-load held-out and ceilings stay commensurate with rebuild-from-corpus."""
    with tempfile.TemporaryDirectory(prefix="lane_mig_") as tmp_a, tempfile.TemporaryDirectory(
        prefix="lane_reb_"
    ) as tmp_b:
        mig = _run_matrix("migrate_load", Path(tmp_a))
        reb = _run_matrix("rebuild_corpus", Path(tmp_b))
    assert _rel_band(mig["scoring"]["heldout_score"], reb["scoring"]["heldout_score"]) <= EVAL_BAND
    assert _ceilings_commensurate(mig, reb)
    assert mig["scoring"]["payload_digest"] == reb["scoring"]["payload_digest"]
    assert len(mig["scoring"]["payload_digest"]) == 64
    assert len(mig["scoring"]["shadow_seal"]) == 64
    assert int(mig["scoring"]["fence_gen"]) >= 1


def test_twin_ceiling_after_fence() -> None:
    """After fence, duplicate upper-half ranks lift ceiling and histogram skew."""
    with tempfile.TemporaryDirectory(prefix="lane_twin_") as tmp:
        twin = _run_matrix("twin_mass", Path(tmp))
    assert _rel_band(float(twin["scoring"]["heldout_score"]), float(twin["scoring"]["baseline_score"])) <= EVAL_BAND
    ceiling = float(twin["draws"][0]["ceiling"])
    span = float(twin["draws"][0]["span"])
    assert span >= ceiling
    assert ceiling >= TWIN_CEILING_MIN
    hist = twin["steps"][-1]["rank_histogram"]
    assert sum(hist) > 0
    upper = sum(hist[len(hist) // 2 :])
    lower = sum(hist[: len(hist) // 2])
    skew = abs(upper - lower) / max(upper + lower, 1)
    assert skew >= TWIN_SKEW_MAX
    assert int(twin["scoring"]["fence_gen"]) >= 1
    assert len(twin["scoring"]["shadow_seal"]) == 64


def test_hybrid_halt_gen_seal() -> None:
    """Halt/continue keeps gen_mark, draw era, and fence_gen aligned with live state."""
    with tempfile.TemporaryDirectory(prefix="lane_halt_") as tmp:
        state = Path(tmp)
        run = _run_matrix("hybrid_halt", state)
        audit = _inspect(state)
    assert audit["gen_mark"] == audit["live_gen"]
    assert audit["halt_step"] > 0
    assert _final_era_matches_live(run, audit)
    assert int(audit["fence_gen"]) == int(run["scoring"]["fence_gen"])
    assert len(audit["shadow_seal"]) == 64
    assert _rel_band(float(run["scoring"]["heldout_score"]), float(run["scoring"]["baseline_score"])) <= EVAL_BAND


def test_torn_journal_recovers_shadow() -> None:
    """Torn trailing journal line recovers with replay_delta 0 and intact shadow seal."""
    with tempfile.TemporaryDirectory(prefix="lane_torn_") as tmp:
        state = Path(tmp)
        run = _run_matrix("torn_resume", state)
        replay = _replay(state, "torn_resume")
    assert float(run["scoring"]["replay_delta"]) == 0.0
    assert len(run["scoring"]["shadow_seal"]) == 64
    assert len(run["scoring"]["payload_digest"]) == 64
    assert int(replay["chain_gap"]) == 0
    assert int(replay["journal_entries"]) > 0
    assert len(replay["shadow_seal"]) == 64
    assert len(replay["replay_stamp"]) == 64


def test_stale_ceiling_after_gen_bump() -> None:
    """After a generation bump, draw eras track live gen and ceilings use full live mass."""
    with tempfile.TemporaryDirectory(prefix="lane_bump_") as tmp:
        run = _run_matrix("gen_bump_ceiling", Path(tmp))
    draws = run["draws"]
    assert len(draws) >= 6
    # Gen advances after the draw at ordinal 5 is recorded; later draws carry era >= 2.
    post = [d for d in draws if int(d["ordinal"]) >= 6]
    assert post
    assert all(int(d["era"]) >= 2 for d in post)
    final_ceil = float(draws[len(draws) - 1]["ceiling"])
    final_span = float(draws[len(draws) - 1]["span"])
    assert final_span >= final_ceil > 0.0
    # Later-biased pack: live-window ceiling must stay high (first-slot-only collapses).
    assert final_ceil >= 0.85
    assert _post_bump_ceilings_stable(draws)


def test_assess_matches_final_scoring() -> None:
    """Assess after migrate stays within eval band of the migrate train held-out."""
    with tempfile.TemporaryDirectory(prefix="lane_assess_") as tmp_a, tempfile.TemporaryDirectory(
        prefix="lane_mig_"
    ) as tmp_b:
        assessed = _run_matrix("assess_after_migrate", Path(tmp_a))
        trained = _run_matrix("migrate_load", Path(tmp_b))
    assert _rel_band(
        float(assessed["scoring"]["heldout_score"]),
        float(trained["scoring"]["heldout_score"]),
    ) <= EVAL_BAND
    assert len(assessed["scoring"]["payload_digest"]) == 64
    assert int(assessed["scoring"]["fence_gen"]) >= 1


def test_double_migrate_shadow_idempotent() -> None:
    """Second migrate/fence leaves shadow_seal, payload_digest, and replay_delta stable."""
    with tempfile.TemporaryDirectory(prefix="lane_dbl_") as tmp:
        run = _run_matrix("double_fence_migrate", Path(tmp))
    scoring = run["scoring"]
    assert len(scoring["shadow_seal"]) == 64
    assert len(scoring["payload_digest"]) == 64
    assert float(scoring["replay_delta"]) == 0.0
    assert int(scoring["fence_gen"]) >= 1
    assert int(scoring["journal_epoch"]) >= 1
    assert _rel_band(float(scoring["heldout_score"]), float(scoring["baseline_score"])) <= EVAL_BAND


def test_halt_twin_order_stable() -> None:
    """Twin-mass setup then halt/continue keeps ceiling skew and gen seal together."""
    with tempfile.TemporaryDirectory(prefix="lane_ht_") as tmp:
        state = Path(tmp)
        run = _run_matrix("halt_twin_order", state)
        audit = _inspect(state)
    ceiling = float(run["draws"][0]["ceiling"])
    assert ceiling >= TWIN_CEILING_MIN
    hist = run["steps"][-1]["rank_histogram"]
    upper = sum(hist[len(hist) // 2 :])
    lower = sum(hist[: len(hist) // 2])
    skew = abs(upper - lower) / max(upper + lower, 1)
    assert skew >= TWIN_SKEW_MAX
    assert audit["gen_mark"] == audit["live_gen"]
    assert _final_era_matches_live(run, audit)
    assert len(audit["shadow_seal"]) == 64
    assert int(audit["fence_gen"]) >= 1


def test_replay_chain_zero_delta() -> None:
    """Replay rebuilds audit from durable bytes with chain_gap 0 and no train advance."""
    with tempfile.TemporaryDirectory(prefix="lane_rep_") as tmp:
        state = Path(tmp)
        run = _run_matrix("migrate_load", state)
        before_ord = _last_step_ordinal(run)
        raw_before = OBS.read_text(encoding="utf-8")
        audit1 = _replay(state, "migrate_load")
        audit2 = _replay(state, "migrate_load")
        raw_after = OBS.read_text(encoding="utf-8")
        after = json.loads(raw_after)
    assert int(audit1["chain_gap"]) == 0
    assert int(audit1["journal_entries"]) > 0
    assert len(audit1["shadow_seal"]) == 64
    assert len(audit1["replay_stamp"]) == 64
    assert audit1 == audit2
    # Replay must not rewrite training observations or advance steps.
    assert raw_before == raw_after
    assert _last_step_ordinal(after["runs"][0]) == before_ord


def test_inspect_bindstamp_stable() -> None:
    """Two inspects agree on bindstamp; seal material is present in the audit."""
    with tempfile.TemporaryDirectory(prefix="lane_ins_") as tmp:
        state = Path(tmp)
        run = _run_matrix("v2_idempotent", state)
        a1 = _inspect(state)
        a2 = _inspect(state)
    assert a1["bindstamp"] == a2["bindstamp"]
    assert len(a1["bindstamp"]) == 64
    assert a1["gen_mark"] == a1["live_gen"]
    assert len(a1["shadow_seal"]) == 64
    assert a1["shadow_seal"] == run["scoring"]["shadow_seal"]
    assert a1["meta_digest"] == a2["meta_digest"]


def test_payload_survives_torn_and_fence() -> None:
    """Payload digest after torn recover matches a clean migrate-load digest."""
    with tempfile.TemporaryDirectory(prefix="lane_pay_a_") as tmp_a, tempfile.TemporaryDirectory(
        prefix="lane_pay_b_"
    ) as tmp_b:
        torn = _run_matrix("torn_resume", Path(tmp_a))
        clean = _run_matrix("migrate_load", Path(tmp_b))
    assert torn["scoring"]["payload_digest"] == clean["scoring"]["payload_digest"]
    assert len(torn["scoring"]["payload_digest"]) == 64
    assert float(torn["scoring"]["replay_delta"]) == 0.0


def test_pipeline_regenerates_artifacts() -> None:
    """Deleted observations regenerate with journal and shadow present (anti-static)."""
    with tempfile.TemporaryDirectory(prefix="lane_pipe_") as tmp:
        state = Path(tmp)
        first = _run_matrix("migrate_load", state)
        raw_first = OBS.read_text(encoding="utf-8")
        OBS.unlink()
        second = _run_matrix("migrate_load", state)
        raw_second = OBS.read_text(encoding="utf-8")
        audit = _inspect(state)
        replay = _replay(state, "migrate_load")
        assert (state / "snap.json").exists()
        assert (state / "journal.ndjson").exists()
        assert (state / "shadow.json").exists()
        shadow = json.loads((state / "shadow.json").read_text(encoding="utf-8"))
    assert raw_first == raw_second
    assert first == second
    assert len(audit["bindstamp"]) == 64
    assert audit["gen_mark"] == audit["live_gen"]
    assert len(shadow["payload_seal"]) == 64
    assert int(shadow["fence_gen"]) >= 1
    assert int(replay["chain_gap"]) == 0
    assert len(replay["replay_stamp"]) == 64
