"""Verifier for ETA residual evaluation ledger and promotion."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path("/app/environment")
ETAENGINE = "/app/environment/bin/etaengine"
OUT = Path("/app/output/run_doc.json")
STATE = ROOT / "state"
MANIFEST = json.loads((ROOT / "assets" / "manifest.json").read_text())
DECLARED_SCALE = float(MANIFEST["declared_scale"])
LIM = 4.0 * DECLARED_SCALE
D1_MIN = 0.08
D1_MAX_FLOOR = 0.12

HELDOUT = {
    "unit": [802, 907, 929, 953],
    "order": [883, 911, 937, 959],
    "pad": [887, 919, 941, 961],
}
FIXTURES = ["batch_00", "batch_01", "batch_02"]
PROD = {
    "scale-mode": "peak",
    "graph-weight": "0.005",
    "lane-weight": "0.995",
}


def _build() -> None:
    subprocess.run(["/app/environment/scripts/build_workspace.sh"], check=True)


def _bin(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([ETAENGINE, *args], check=True, capture_output=True, text=True)


def _reset_state() -> None:
    # restore from image-baked copy kept beside assets
    baked = ROOT / "assets" / "registry_init.json"
    if baked.exists():
        STATE.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(baked, STATE / "registry.json")
    staged = STATE / "staged.json"
    if staged.exists():
        staged.unlink()
    ledger = STATE / "ledger.jsonl"
    if ledger.exists():
        ledger.unlink()


def _promote_prod() -> None:
    _bin(["stage", "--root", str(ROOT), "--scale-mode", PROD["scale-mode"],
          "--graph-weight", PROD["graph-weight"], "--lane-weight", PROD["lane-weight"]])
    _bin(["finalize", "--root", str(ROOT)])
    _bin(["commit", "--root", str(ROOT)])


def _evaluate(fixture: str, family: str, seed: int, key: str | None = None) -> dict:
    if OUT.exists():
        OUT.unlink()
    args = [
        "evaluate", "--root", str(ROOT), "--fixture", fixture, "--family", family,
        "--seed", str(seed), "--out", str(OUT),
    ]
    if key:
        args.extend(["--key", key])
    _bin(args)
    return json.loads(OUT.read_text())


def _reg() -> dict:
    return json.loads((STATE / "registry.json").read_text())


def _t1(a: float, b: float) -> float:
    return max(1e-4, 0.008 * max(abs(a), abs(b), 1.0))


def _rows(doc: dict) -> list[dict]:
    return sorted(doc["runs"], key=lambda r: r["instance_id"])


def _assert_t1(base: dict, pert: dict) -> None:
    bd = [float(r["delta"]) for r in _rows(base)]
    pd = [float(r["delta"]) for r in _rows(pert)]
    assert len(bd) == len(pd) >= 2
    for d0, d1 in zip(bd, pd):
        assert abs(d0 - d1) <= _t1(d0, d1)


def _assert_d1(doc: dict) -> None:
    mags = [abs(float(r["score"])) for r in doc["runs"]]
    assert max(mags) > D1_MAX_FLOOR
    for m in mags:
        assert m > D1_MIN
    for r in doc["runs"]:
        assert abs(float(r["score"])) <= LIM + 1e-3


def _assert_gen(doc: dict, gen: int) -> None:
    assert int(doc["summary"]["generation"]) == gen
    for r in doc["runs"]:
        assert int(r["generation"]) == gen


@pytest.fixture(scope="module", autouse=True)
def _setup():
    _build()
    # bake init snapshot once
    init = ROOT / "assets" / "registry_init.json"
    if not init.exists():
        shutil.copyfile(STATE / "registry.json", init)


def test_g1_prod_settings_unit_t1_d1():
    """After production cutover, unit family stays inside T1 and D1."""
    _reset_state()
    _promote_prod()
    gen = int(_reg()["active_generation"])
    for fx in FIXTURES:
        for seed in HELDOUT["unit"]:
            base = _evaluate(fx, "base", 0)
            pert = _evaluate(fx, "unit", seed)
            _assert_t1(base, pert)
            _assert_d1(pert)
            _assert_gen(pert, gen)


def test_g2_order_pad_t1():
    """Order and pad families stay T1-close to base after production settings activate."""
    _reset_state()
    _promote_prod()
    for fx in FIXTURES:
        base = _evaluate(fx, "base", 0)
        for seed in HELDOUT["order"]:
            pert = _evaluate(fx, "order", seed)
            _assert_t1(base, pert)
            _assert_d1(pert)
        for seed in HELDOUT["pad"]:
            pert = _evaluate(fx, "pad", seed)
            _assert_t1(base, pert)
            _assert_d1(pert)


def test_h3_incomplete_stage_ignored_by_evaluate():
    """Evaluate ignores incomplete staged settings and keeps active generation."""
    _reset_state()
    before = _reg()
    _bin(["stage", "--root", str(ROOT), "--scale-mode", "peak",
          "--graph-weight", "0.005", "--lane-weight", "0.995"])
    assert (STATE / "staged.json").exists()
    staged = json.loads((STATE / "staged.json").read_text())
    assert staged["incomplete"] is True
    doc = _evaluate("batch_02", "base", 0)
    assert int(doc["summary"]["generation"]) == int(before["active_generation"])
    assert int(_reg()["active_generation"]) == int(before["active_generation"])
    # Active gen-0 declared settings must remain in force — D1 must not pass yet.
    mags = [abs(float(r["score"])) for r in doc["runs"]]
    assert max(mags) <= D1_MAX_FLOOR


def test_h4_commit_requires_finalize():
    """Commit without finalize must fail and leave registry generation unchanged."""
    _reset_state()
    before = int(_reg()["active_generation"])
    _bin(["stage", "--root", str(ROOT), "--scale-mode", "peak",
          "--graph-weight", "0.005", "--lane-weight", "0.995"])
    with pytest.raises(subprocess.CalledProcessError):
        _bin(["commit", "--root", str(ROOT)])
    assert int(_reg()["active_generation"]) == before


def test_c5_commit_clears_staged_and_records_history():
    """Successful commit clears staged.json and stores settings_by_gen."""
    _reset_state()
    _promote_prod()
    assert not (STATE / "staged.json").exists()
    reg = _reg()
    gen = str(reg["active_generation"])
    assert gen in reg["settings_by_gen"]
    assert reg["settings_by_gen"][gen]["scale_mode"] == "peak"


def test_c6_rollback_restores_settings():
    """Rollback restores prior settings from settings_by_gen."""
    _reset_state()
    _promote_prod()
    mid = _reg()
    assert mid["settings"]["scale_mode"] == "peak"
    _bin(["rollback", "--root", str(ROOT)])
    after = _reg()
    assert int(after["active_generation"]) == int(mid["active_generation"]) - 1
    assert after["settings"]["scale_mode"] == "declared"
    assert not (STATE / "staged.json").exists()


def test_s7_replay_rescores_after_prod_settings():
    """Replay after settings activate must not copy stale pre-activate output bytes."""
    _reset_state()
    key = "batch_00:base:0"
    pre_out = Path("/app/output/pre_replay.json")
    if pre_out.exists():
        pre_out.unlink()
    _bin([
        "evaluate", "--root", str(ROOT), "--fixture", "batch_00", "--family", "base",
        "--seed", "0", "--out", str(pre_out), "--key", key,
    ])
    pre = json.loads(pre_out.read_text())
    pre_scores = [float(r["score"]) for r in _rows(pre)]
    assert pre_out.exists()
    _promote_prod()
    if OUT.exists():
        OUT.unlink()
    _bin(["replay", "--root", str(ROOT), "--key", key, "--out", str(OUT)])
    post = json.loads(OUT.read_text())
    post_scores = [float(r["score"]) for r in _rows(post)]
    assert post_scores != pre_scores
    _assert_d1(post)
    _assert_gen(post, int(_reg()["active_generation"]))
    # Stale bytes at the original out_path must remain untouched by a correct rescore.
    assert [float(r["score"]) for r in _rows(json.loads(pre_out.read_text()))] == pre_scores


def test_s8_schema_and_delta_identity():
    """Schema fields and delta identity hold under active generation."""
    _reset_state()
    _promote_prod()
    doc = _evaluate("batch_01", "unit", HELDOUT["unit"][1])
    assert doc["version"] == 1
    assert len(doc["runs"]) == 2
    assert doc["summary"]["instance_count"] == 2
    assert "model_id" in doc["summary"]
    for row in doc["runs"]:
        assert abs(float(row["delta"]) - (float(row["score"]) - float(row["observed"]))) <= 1e-5
        assert row["profile"] == "alpha"
    _assert_d1(doc)


def test_o9_score_ordering():
    """Score ordering holds for promoted evaluations."""
    _reset_state()
    _promote_prod()
    for fx in FIXTURES:
        doc = _evaluate(fx, "order", HELDOUT["order"][2])
        rows = _rows(doc)
        for i in range(len(rows) - 1):
            a, b = rows[i], rows[i + 1]
            if float(b["observed"]) >= float(a["observed"]):
                assert float(a["score"]) - float(b["score"]) <= 0.05 + 1e-6
        _assert_d1(doc)


def test_x10_idempotent_evaluate_key():
    """Re-evaluate with same key remains deterministic under active generation."""
    _reset_state()
    _promote_prod()
    key = "batch_01:pad:887"
    d1 = _evaluate("batch_01", "pad", 887, key=key)
    d2 = _evaluate("batch_01", "pad", 887, key=key)
    assert d1 == d2
    _assert_d1(d1)
    _assert_gen(d1, int(_reg()["active_generation"]))
    assert _reg()["settings"]["scale_mode"] == "peak"

def test_x11_authority_after_interrupted_stage():
    """Decisive: stage without finalize, evaluate stays on old gen; finalize+commit then flips."""
    _reset_state()
    old = _evaluate("batch_02", "unit", 802)
    old_gen = int(old["summary"]["generation"])
    old_mags = [abs(float(r["score"])) for r in old["runs"]]
    assert max(old_mags) <= D1_MAX_FLOOR
    _bin(["stage", "--root", str(ROOT), "--scale-mode", "peak",
          "--graph-weight", "0.005", "--lane-weight", "0.995"])
    mid = _evaluate("batch_02", "unit", 802)
    assert int(mid["summary"]["generation"]) == old_gen
    mid_mags = [abs(float(r["score"])) for r in mid["runs"]]
    assert max(mid_mags) <= D1_MAX_FLOOR
    _bin(["finalize", "--root", str(ROOT)])
    _bin(["commit", "--root", str(ROOT)])
    new = _evaluate("batch_02", "unit", 802)
    assert int(new["summary"]["generation"]) == old_gen + 1
    _assert_d1(new)
    base = _evaluate("batch_02", "base", 0)
    _assert_t1(base, new)


def test_x12_fixtures_untouched():
    """Fixture bytes remain unchanged across settings activate and evaluate."""
    before = {p.read_bytes() for p in (ROOT / "testsupport" / "fixtures").glob("*.json")}
    _reset_state()
    _promote_prod()
    _evaluate("batch_00", "order", 883)
    after = {p.read_bytes() for p in (ROOT / "testsupport" / "fixtures").glob("*.json")}
    assert before == after
