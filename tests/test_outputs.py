"""Independent verifier for ferric HPO log archaeology emits."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest

APP = Path("/app/environment")
EMIT = Path("/app/emit")
SHEET = EMIT / "rung_sheet.json"
LEDGER = EMIT / "align_ledger.json"
TOL = 1e-9

SLAG = APP / "slag" / "src" / "slag_bind.rs"
KILN = APP / "kiln" / "src" / "kiln_forge.rs"


def near(a: float, b: float) -> bool:
    return abs(float(a) - float(b)) <= TOL


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def halt_flag(tag: str) -> bool:
    t = tag.strip().lower()
    return t in {"e", "cut", "halted"}


def eta_expected(lr0: float, gamma: float, period: int, step: int) -> float:
    p = period if period else 1
    return lr0 * (gamma ** (step // p))


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def forge_score(
    aid: str, lr0: float, gamma: float, period: int, bag: dict[str, Any], nest_outer: str
) -> float:
    s = f"{aid}|{lr0:.10f}|{gamma:.10f}|{period}|{bag['knob']}|{bag['salt']}|{nest_outer}"
    dig = hashlib.sha256(s.encode("utf-8")).digest()
    v = int.from_bytes(dig[:8], "big", signed=False)
    return v / float((1 << 64) - 1)


def load_traces() -> list[dict[str, Any]]:
    runs = APP / "data" / "runs"
    paths = sorted(
        p
        for p in runs.glob("*.jsonl")
        if p.name != "side_bag.jsonl"
    )
    rows: list[dict[str, Any]] = []
    for p in paths:
        rows.extend(load_jsonl(p))
    return rows


def load_side() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(APP / "data" / "runs" / "side_bag.jsonl"):
        out[row["rid"]] = row
    return out


def reconcile(
    traces: list[dict[str, Any]], side: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in traces:
        score = float(r["vis"])
        from_side = False
        s = side.get(r["rid"])
        if s is not None and int(s["hid"]) == 1:
            score = float(s["true_vis"])
            from_side = True
        out.append(
            {
                "rid": r["rid"],
                "aid": r["aid"],
                "step": int(r["step"]),
                "eta": float(r["eta"]),
                "score": score,
                "halted": halt_flag(str(r["halt"])),
                "from_side": from_side,
                "nest": r["nest"],
                "lr0": float(r["lr0"]),
                "gamma": float(r["gamma"]),
                "period": int(r["period"]),
            }
        )
    out.sort(key=lambda x: (x["aid"], x["step"], x["rid"]))
    return out


def bind(
    sift: list[dict[str, Any]],
    grid: dict[str, Any],
    nest: dict[str, Any],
) -> dict[str, Any]:
    by_aid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in sift:
        by_aid[r["aid"]].append(r)
    arms: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    ended_aids: set[str] = set()
    triples = grid["triples"]
    for aid, rows in by_aid.items():
        outer_counts: dict[str, int] = defaultdict(int)
        for r in rows:
            e = nest.get(r["nest"])
            if e:
                outer_counts[e["outer"]] += 1
        if not outer_counts:
            continue
        mode_outer = min(outer_counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        kept = [
            r
            for r in rows
            if nest.get(r["nest"]) and nest[r["nest"]]["outer"] == mode_outer
        ]
        if not kept:
            continue
        kept.sort(key=lambda x: (x["step"], x["rid"]))
        lr0 = kept[0]["lr0"]
        gamma = kept[0]["gamma"]
        period = kept[0]["period"]
        if any(
            not near(r["lr0"], lr0) or not near(r["gamma"], gamma) or r["period"] != period
            for r in kept
        ):
            continue
        if not any(
            near(t["lr0"], lr0) and near(t["gamma"], gamma) and int(t["period"]) == period
            for t in triples
        ):
            continue
        if any(not near(r["eta"], eta_expected(lr0, gamma, period, r["step"])) for r in kept):
            continue
        p = period if period else 1
        rung_total = sum(r["score"] for r in kept if r["step"] % p == 0)
        ended = bool(kept[-1]["halted"])
        cases.extend(kept)
        arms.append(
            {
                "aid": aid,
                "rung_total": rung_total,
                "lr0": lr0,
                "gamma": gamma,
                "period": period,
                "nest_outer": mode_outer,
            }
        )
        if ended:
            ended_aids.add(aid)
    arms.sort(key=lambda a: a["aid"])
    cases.sort(key=lambda c: c["rid"])
    eligible = [a for a in arms if a["aid"] not in ended_aids]
    best_aid = ""
    if eligible:
        eligible.sort(key=lambda a: (-a["rung_total"], a["aid"]))
        best_aid = eligible[0]["aid"]
    return {"arms": arms, "best_aid": best_aid, "cases": cases, "nest": nest}


def sheet_digest(arms: list[dict[str, Any]]) -> str:
    blob = ""
    for a in sorted(arms, key=lambda x: x["aid"]):
        blob += (
            f"aid={a['aid']};rung={a['rung_total']:.10f};lr0={a['lr0']:.10f};"
            f"gamma={a['gamma']:.10f};period={a['period']};outer={a['nest_outer']}\n"
        )
    return sha256_hex(blob)


def ledger_digest(cases: list[dict[str, Any]], nest: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    led: list[dict[str, Any]] = []
    for r in sorted(cases, key=lambda x: x["rid"]):
        e = nest.get(r["nest"], {"outer": "", "inner": ""})
        led.append(
            {
                "rid": r["rid"],
                "aid": r["aid"],
                "score_used": r["score"],
                "from_side": r["from_side"],
                "nest_outer": e["outer"],
                "nest_inner": e["inner"],
                "halted": r["halted"],
            }
        )
    blob = ""
    for c in led:
        blob += (
            f"rid={c['rid']};score={c['score_used']:.10f};"
            f"side={1 if c['from_side'] else 0};outer={c['nest_outer']};"
            f"inner={c['nest_inner']};halt={1 if c['halted'] else 0}\n"
        )
    return sha256_hex(blob), led


def expected_artifacts(
    nest_path: Path | None = None, grid_path: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    nest = json.loads((nest_path or APP / "data" / "nests" / "nest_map.json").read_text())
    grid = json.loads((grid_path or APP / "data" / "grids" / "grid_pub.json").read_text())
    bag = json.loads((APP / "data" / "bags" / "forge_bag.json").read_text())
    sift = reconcile(load_traces(), load_side())
    bound = bind(sift, grid, nest)
    arms = [
        {
            "aid": a["aid"],
            "rung_total": a["rung_total"],
            "lr0": a["lr0"],
            "gamma": a["gamma"],
            "period": a["period"],
            "nest_outer": a["nest_outer"],
        }
        for a in bound["arms"]
    ]
    dig_s = sheet_digest(arms)
    dig_l, led_cases = ledger_digest(bound["cases"], nest)
    best = next((a for a in bound["arms"] if a["aid"] == bound["best_aid"]), None)
    if best is None:
        score = 0.0
        nest_outer = ""
    else:
        score = forge_score(
            best["aid"], best["lr0"], best["gamma"], best["period"], bag, best["nest_outer"]
        )
        nest_outer = best["nest_outer"]
    sheet = {
        "version": 1,
        "arms": arms,
        "best_aid": bound["best_aid"],
        "sheet_digest": dig_s,
    }
    ledger = {
        "version": 1,
        "cases": led_cases,
        "ledger_digest": dig_l,
        "forge": {
            "bag_id": bag["bag_id"],
            "aid": bound["best_aid"],
            "score": score,
            "nest_outer": nest_outer,
        },
    }
    return sheet, ledger


def run_drv(env: dict[str, str] | None = None) -> None:
    EMIT.mkdir(parents=True, exist_ok=True)
    for p in (SHEET, LEDGER):
        if p.exists():
            p.unlink()
    cmd_env = dict(os.environ)
    if env:
        cmd_env.update(env)
    subprocess.run(
        [str(APP / "run_ferric_drv")],
        check=True,
        cwd=str(APP),
        env=cmd_env,
    )


def read_emits() -> tuple[dict[str, Any], dict[str, Any]]:
    return json.loads(SHEET.read_text()), json.loads(LEDGER.read_text())


def cargo_build() -> None:
    subprocess.run(
        ["cargo", "build", "--release", "--bin", "ferric_drv"],
        check=True,
        cwd=str(APP),
        env={**os.environ, "CARGO_TARGET_DIR": "/tmp/ferric-target"},
    )


@pytest.fixture(scope="module", autouse=True)
def _ensure_build() -> None:
    # Rebuild in case oracle or ablations changed sources.
    cargo_build()


def test_h7_c01_shape() -> None:
    """Emit schemas and best_aid match recomputed contract."""
    run_drv()
    sheet, ledger = read_emits()
    exp_s, _exp_l = expected_artifacts()
    assert sheet["version"] == 1
    assert ledger["version"] == 1
    assert isinstance(sheet["arms"], list) and sheet["arms"]
    assert isinstance(ledger["cases"], list) and ledger["cases"]
    assert "sheet_digest" in sheet and "ledger_digest" in ledger
    assert "forge" in ledger
    assert sheet["best_aid"] == exp_s["best_aid"]
    assert {a["aid"] for a in sheet["arms"]} == {a["aid"] for a in exp_s["arms"]}


def test_h7_c02_twin() -> None:
    """Twin runs agree on sheet/ledger digests and forge score."""
    run_drv()
    s1, l1 = read_emits()
    run_drv()
    s2, l2 = read_emits()
    assert s1["sheet_digest"] == s2["sheet_digest"]
    assert l1["ledger_digest"] == l2["ledger_digest"]
    assert near(l1["forge"]["score"], l2["forge"]["score"])
    exp_s, exp_l = expected_artifacts()
    assert s1["sheet_digest"] == exp_s["sheet_digest"]
    assert l1["ledger_digest"] == exp_l["ledger_digest"]
    assert near(l1["forge"]["score"], exp_l["forge"]["score"])


def test_h7_c03_nestmap() -> None:
    """Nestmap outer lineage changes held-out rung totals."""
    run_drv()
    sheet, _ledger = read_emits()
    exp_s, _exp_l = expected_artifacts()
    # Public nestmap excludes N3x from a3 outer mode.
    a3 = next(a for a in sheet["arms"] if a["aid"] == "a3")
    exp_a3 = next(a for a in exp_s["arms"] if a["aid"] == "a3")
    assert a3["nest_outer"] == exp_a3["nest_outer"]
    assert near(a3["rung_total"], exp_a3["rung_total"])
    # Held-out nestmap merges N3x into the mode outer and must change a3 rung total.
    hold_s, _ = expected_artifacts(nest_path=APP / "data" / "nests" / "nest_hold.json")
    hold_a3 = next(a for a in hold_s["arms"] if a["aid"] == "a3")
    assert not near(hold_a3["rung_total"], a3["rung_total"])
    nest_override = APP / "data" / "nests" / "nest_hold.json"
    key = "FERRIC" + "_" + "NEST"
    run_drv(env={key: str(nest_override)})
    sheet2, _ = read_emits()
    a3b = next(a for a in sheet2["arms"] if a["aid"] == "a3")
    assert near(a3b["rung_total"], hold_a3["rung_total"])


def test_h7_c04_rungsem() -> None:
    """LR rung totals and eta law match the published schedule contract."""
    run_drv()
    sheet, _ = read_emits()
    exp_s, _ = expected_artifacts()
    for a in sheet["arms"]:
        e = next(x for x in exp_s["arms"] if x["aid"] == a["aid"])
        assert near(a["rung_total"], e["rung_total"])
        assert near(a["lr0"], e["lr0"])
        assert near(a["gamma"], e["gamma"])
        assert int(a["period"]) == int(e["period"])
        # Spot-check eta law on public traces for this aid.
        for row in load_traces():
            if row["aid"] != a["aid"]:
                continue
            expect = eta_expected(a["lr0"], a["gamma"], int(a["period"]), int(row["step"]))
            assert near(float(row["eta"]), expect)


def test_h7_c05_sidehide() -> None:
    """Sidecar hid scores are recovered; summary peaks do not win."""
    run_drv()
    _, ledger = read_emits()
    _, exp_l = expected_artifacts()
    side_cases = [c for c in ledger["cases"] if c["from_side"]]
    assert side_cases, "sidecar recovery must mark from_side cases"
    by_rid = {c["rid"]: c for c in ledger["cases"]}
    for rid, srow in load_side().items():
        if int(srow["hid"]) != 1:
            continue
        assert rid in by_rid
        assert by_rid[rid]["from_side"] is True
        assert near(by_rid[rid]["score_used"], float(srow["true_vis"]))
    # Summary peak for a2 must not become best_aid after recovery + halt.
    sheet, _ = read_emits()
    assert sheet["best_aid"] == exp_l["forge"]["aid"]
    assert sheet["best_aid"] == "a1"
    assert sheet["best_aid"] != "a2"


def test_h7_c06_write_trap() -> None:
    """Hand-edited emits are overwritten by a rebuild."""
    run_drv()
    sheet, ledger = read_emits()
    # Mutate artifacts in place.
    sheet["best_aid"] = sheet["best_aid"] + sheet["best_aid"]
    sheet["sheet_digest"] = "0" * 64
    ledger["forge"]["score"] = 0.0
    ledger["ledger_digest"] = "1" * 64
    SHEET.write_text(json.dumps(sheet))
    LEDGER.write_text(json.dumps(ledger))
    run_drv()
    s2, l2 = read_emits()
    exp_s, exp_l = expected_artifacts()
    assert s2["best_aid"] == exp_s["best_aid"]
    assert s2["sheet_digest"] == exp_s["sheet_digest"]
    assert l2["ledger_digest"] == exp_l["ledger_digest"]
    assert near(l2["forge"]["score"], exp_l["forge"]["score"])


def test_h7_c07_ablate_a() -> None:
    """Ablating the bind path flips nestmap and rung observations."""
    bak = SLAG.read_text()
    try:
        snaps = sorted((APP / "lib").glob("snap_*.rs"))
        shutil.copy(snaps[0], SLAG)
        cargo_build()
        run_drv()
        sheet, _ = read_emits()
        exp_s, _ = expected_artifacts()
        bad = False
        if sheet["best_aid"] != exp_s["best_aid"]:
            bad = True
        for a in sheet["arms"]:
            match = next((x for x in exp_s["arms"] if x["aid"] == a["aid"]), None)
            if match is None or not near(a["rung_total"], match["rung_total"]):
                bad = True
            if match is None or a.get("nest_outer") != match["nest_outer"]:
                bad = True
        assert bad, "ablating bind path must flip nestmap/rung subset"
    finally:
        SLAG.write_text(bak)
        cargo_build()


def test_h7_c08_ablate_b() -> None:
    """Ablating the cast path flips digest and holdout forge observations."""
    bak = KILN.read_text()
    try:
        snaps = sorted((APP / "lib").glob("snap_*.rs"))
        shutil.copy(snaps[1], KILN)
        cargo_build()
        run_drv()
        s, led = read_emits()
        exp_s, exp_l = expected_artifacts()
        assert s["sheet_digest"] != exp_s["sheet_digest"] or not near(
            led["forge"]["score"], exp_l["forge"]["score"]
        )
    finally:
        KILN.write_text(bak)
        cargo_build()
