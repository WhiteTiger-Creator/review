"""Verifier for YINSH championship report output."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

SCENARIOS = Path("/app/scenarios")
OUTPUT = Path("/app/output/championship_report.json")
CONTRACT = Path("/app/contracts/championship-ruleset.md")
PROFILE = Path("/app/config/profiles/champ-v3/rules.toml")
PROFILE_NAME = Path("/app/config/profile.name")
BINARY = Path("/app/bin/yinsh-ring")

RUN_ID = "yinsh-champ-v1"
CORRECT = {
    "run_id": RUN_ID,
    "row_length": 5,
    "rings_to_win": 3,
    "rings_start": 5,
    "flip_enabled": 1,
    "leave_marker": 1,
    "win_points": 3,
    "draw_points": 1,
}
CORRECT_SEAL = "063467fd701342809041f9cbb843d8e83772f6076602cd1c772257a1cbd9095d"

SCENARIO_SHA256 = {
    "m01.json": "116e045f409e580f6362eee6bcb5d217d836066c69c42bf0c3647652dcfc2078",
    "m02.json": "0a2425a211df31f54e83211adb79ff3e58fed63adcc44d6df11bae44f4bf6bc2",
    "m03.json": "82efa601cbd23338e7aa2bb04b0b69a21f7462f52dc63f1c502789d6956799e9",
    "m04.json": "a4b026c297536bb4c4e195eaf3874878ad18e89069e21b261aafb66177e6bb04",
    "m05.json": "69cc53e64c70aeeffd0719a8f411e7c968ca9cdc0fb39eb261d7da2c30a61b92",
    "m06.json": "1a7545fa98fd14b9c997046bfc560e62ea977a0d1c1f7334e750b80a094a158b",
    "m07.json": "299f6033ee5a011f9b152a63429f8657801b342aca486e7040f5537eb1c09994",
    "m08.json": "16523f7c1eb11659f3ba0ef825b4767ea3db55cbe788a46bc8a4f96205b30715",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _half_away_round(x: float) -> int:
    if x >= 0:
        return math.floor(x + 0.5)
    return math.ceil(x - 0.5)


def _config_seal(cfg: dict) -> str:
    keys = [
        "run_id",
        "row_length",
        "rings_to_win",
        "rings_start",
        "flip_enabled",
        "leave_marker",
        "win_points",
        "draw_points",
    ]
    payload = "".join(f"{k}={cfg[k]}\n" for k in keys)
    return hashlib.sha256(payload.encode()).hexdigest()


def _color(side: str) -> int:
    return 1 if side == "A" else 2


def _find_row(markers: list[int], side: str, row_len: int, lines: list[list[int]]) -> list[int] | None:
    want = _color(side)
    for line in lines:
        if len(line) < row_len:
            continue
        for start in range(len(line) - row_len + 1):
            window = line[start : start + row_len]
            if all(markers[i] == want for i in window):
                return list(window)
    return None


def _sim(scenario: dict, cfg: dict) -> dict:
    markers = list(scenario["markers"])
    rings_a = list(scenario["rings_a"])
    rings_b = list(scenario["rings_b"])
    rem_a = rem_b = 0
    flips = {"A": 0, "B": 0}
    rows = {"A": 0, "B": 0}
    lines = scenario["lines"]
    for mv in scenario["moves"]:
        side = mv.get("side") or "A"
        frm = mv["from"]
        to = mv["to"]
        path = mv.get("path") or []
        own = rings_a if side == "A" else rings_b
        if frm not in own:
            continue
        if to in rings_a or to in rings_b:
            continue
        if cfg["leave_marker"] == 1:
            markers[frm] = _color(side)
        own.remove(frm)
        own.append(to)
        if side == "A":
            rings_a = own
        else:
            rings_b = own
        if cfg["flip_enabled"] == 1:
            for p in path:
                if markers[p] == 1:
                    markers[p] = 2
                    flips[side] += 1
                elif markers[p] == 2:
                    markers[p] = 1
                    flips[side] += 1
        window = _find_row(markers, side, cfg["row_length"], lines)
        if window:
            rows[side] += 1
            for i in window:
                markers[i] = 0
            remove_at = mv.get("remove_ring", -1)
            if remove_at in own:
                own.remove(remove_at)
            elif own:
                own.sort()
                own.pop(0)
            if side == "A":
                rings_a = own
                rem_a += 1
            else:
                rings_b = own
                rem_b += 1
            if rem_a >= cfg["rings_to_win"] or rem_b >= cfg["rings_to_win"]:
                break
    return {
        "rings_removed_a": rem_a,
        "rings_removed_b": rem_b,
        "flips_a": flips["A"],
        "flips_b": flips["B"],
        "rows_cleared_a": rows["A"],
        "rows_cleared_b": rows["B"],
        "rings_left_a": len(rings_a),
        "rings_left_b": len(rings_b),
    }


def _decide(res: dict, cfg: dict) -> tuple[str, str]:
    ra, rb = res["rings_removed_a"], res["rings_removed_b"]
    if ra >= cfg["rings_to_win"] or rb >= cfg["rings_to_win"]:
        if ra >= cfg["rings_to_win"] and rb >= cfg["rings_to_win"]:
            if ra > rb:
                return "A", "ring_target"
            if rb > ra:
                return "B", "ring_target"
            return "draw", "mutual_draw"
        if ra >= cfg["rings_to_win"]:
            return "A", "ring_target"
        return "B", "ring_target"
    if ra != rb:
        return ("A" if ra > rb else "B"), "ring_majority"
    return "draw", "mutual_draw"


def _score(reason: str) -> tuple[str, int]:
    if reason == "ring_target":
        return "critical", 94
    if reason == "ring_majority":
        return "high", 68
    return "low", 18


def _severity_rank(s: str) -> int:
    return {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}.get(s, 0)


def _load_scenarios() -> list[dict]:
    out = []
    for path in sorted(SCENARIOS.glob("*.json")):
        out.append(json.loads(path.read_text()))
    out.sort(key=lambda s: s["match_id"])
    return out


def _expected_report() -> dict:
    cfg = CORRECT
    scenarios = _load_scenarios()
    matches = []
    for sc in scenarios:
        res = _sim(sc, cfg)
        winner, reason = _decide(res, cfg)
        if winner == "A":
            pa, pb = cfg["win_points"], 0
        elif winner == "B":
            pa, pb = 0, cfg["win_points"]
        else:
            pa = pb = cfg["draw_points"]
        sev, sc_score = _score(reason)
        matches.append(
            {
                "match_id": sc["match_id"],
                "player_a": sc["player_a"],
                "player_b": sc["player_b"],
                "winner": winner,
                "reason": reason,
                "rings_removed_a": res["rings_removed_a"],
                "rings_removed_b": res["rings_removed_b"],
                "flips_a": res["flips_a"],
                "flips_b": res["flips_b"],
                "rows_cleared_a": res["rows_cleared_a"],
                "rows_cleared_b": res["rows_cleared_b"],
                "rings_left_a": res["rings_left_a"],
                "rings_left_b": res["rings_left_b"],
                "points_a": pa,
                "points_b": pb,
                "severity": sev,
                "priority_score": sc_score,
                "related_ids": [],
            }
        )
    by_player: dict[str, list[str]] = {}
    for m in matches:
        by_player.setdefault(m["player_a"], []).append(m["match_id"])
        by_player.setdefault(m["player_b"], []).append(m["match_id"])
    for m in matches:
        rel = set()
        for pid in (m["player_a"], m["player_b"]):
            for mid in by_player[pid]:
                if mid != m["match_id"]:
                    rel.add(mid)
        m["related_ids"] = sorted(rel)

    tab: dict[str, dict] = {}
    for m in matches:
        for pid, pts, rem_own, rem_opp in (
            (m["player_a"], m["points_a"], m["rings_removed_a"], m["rings_removed_b"]),
            (m["player_b"], m["points_b"], m["rings_removed_b"], m["rings_removed_a"]),
        ):
            row = tab.setdefault(
                pid, {"points": 0, "wins": 0, "draws": 0, "losses": 0, "ring_diff": 0}
            )
            row["points"] += pts
            row["ring_diff"] += rem_own - rem_opp
            if m["winner"] == "draw":
                row["draws"] += 1
            elif (pid == m["player_a"] and m["winner"] == "A") or (
                pid == m["player_b"] and m["winner"] == "B"
            ):
                row["wins"] += 1
            else:
                row["losses"] += 1

    ids = sorted(
        tab.keys(),
        key=lambda pid: (-tab[pid]["points"], -tab[pid]["ring_diff"], pid),
    )
    standings = []
    for rank, pid in enumerate(ids, start=1):
        a = tab[pid]
        standings.append(
            {
                "player_id": pid,
                "points": a["points"],
                "wins": a["wins"],
                "draws": a["draws"],
                "losses": a["losses"],
                "ring_diff": a["ring_diff"],
                "rank": rank,
            }
        )

    mean = sum(m["priority_score"] for m in matches) / len(matches)
    agg = min(100, _half_away_round(mean * 1.25))
    max_sev = "none"
    dec = drw = 0
    for m in matches:
        if _severity_rank(m["severity"]) > _severity_rank(max_sev):
            max_sev = m["severity"]
        if m["winner"] == "draw":
            drw += 1
        else:
            dec += 1

    return {
        "schema_version": "1.0",
        "run_id": cfg["run_id"],
        "matches_played": len(matches),
        "matches": matches,
        "standings": standings,
        "summary": {
            "aggregate_priority": agg,
            "max_severity": max_sev,
            "decisive_matches": dec,
            "draw_matches": drw,
        },
    }


def _parse_profile(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"')
    return out


def _run_engine() -> None:
    subprocess.run(
        [
            str(BINARY),
            "--scenarios",
            str(SCENARIOS),
            "--config",
            "/app/config",
            "--out",
            "/app/output",
        ],
        check=True,
    )


def _load_report() -> dict:
    return json.loads(OUTPUT.read_text())


def test_scenario_fixtures_unchanged():
    """Scenario fixture bytes must match the pinned SHA-256 digests."""
    for name, digest in SCENARIO_SHA256.items():
        assert _sha256(SCENARIOS / name) == digest


def test_contract_and_profile_name_present():
    """Contract file exists and profile.name selects champ-v3."""
    assert CONTRACT.is_file()
    assert PROFILE_NAME.read_text().strip() == "champ-v3"


def test_sealed_profile_floors_and_seal():
    """Sealed profile carries championship floors with a matching config_seal."""
    text = PROFILE.read_text()
    for line in (
        'run_id = "yinsh-champ-v1"',
        "row_length = 5",
        "rings_to_win = 3",
        "rings_start = 5",
        "flip_enabled = 1",
        "leave_marker = 1",
        "win_points = 3",
        "draw_points = 1",
        f'config_seal = "{CORRECT_SEAL}"',
    ):
        assert line in text
    parsed = _parse_profile(text)
    cfg = {k: (parsed[k] if k == "run_id" else int(parsed[k])) for k in CORRECT}
    assert _config_seal(cfg) == CORRECT_SEAL
    assert parsed["config_seal"] == CORRECT_SEAL


def test_seal_mismatch_uses_championship_baseline():
    """Corrupting config_seal still yields championship floors via runtime baseline."""
    original = PROFILE.read_text()
    try:
        lines = []
        for line in original.splitlines():
            if line.strip().startswith("config_seal"):
                lines.append('config_seal = "' + ("0" * 64) + '"')
            else:
                lines.append(line)
        PROFILE.write_text("\n".join(lines) + "\n")
        _run_engine()
        got = _load_report()
        exp = _expected_report()
        assert got["run_id"] == RUN_ID
        assert got["matches"] == exp["matches"]
        assert got["standings"] == exp["standings"]
        assert got["summary"] == exp["summary"]
    finally:
        PROFILE.write_text(original)
        _run_engine()


def test_report_schema_and_run_id():
    """Report exposes the documented schema keys and championship run_id."""
    rep = _load_report()
    assert rep["schema_version"] == "1.0"
    assert rep["run_id"] == RUN_ID
    assert set(rep) >= {"schema_version", "run_id", "matches_played", "matches", "standings", "summary"}
    assert rep["matches_played"] == len(rep["matches"])
    for m in rep["matches"]:
        assert set(m) >= {
            "match_id",
            "player_a",
            "player_b",
            "winner",
            "reason",
            "rings_removed_a",
            "rings_removed_b",
            "flips_a",
            "flips_b",
            "rows_cleared_a",
            "rows_cleared_b",
            "rings_left_a",
            "rings_left_b",
            "points_a",
            "points_b",
            "severity",
            "priority_score",
            "related_ids",
        }


def test_match_outcomes_match_ruleset_simulation():
    """Each match row matches an independent ruleset simulation."""
    got = _load_report()["matches"]
    exp = _expected_report()["matches"]
    assert got == exp


def test_related_ids_share_players():
    """related_ids lists other matches sharing a player, sorted ascending."""
    got = _load_report()["matches"]
    exp = _expected_report()["matches"]
    for g, e in zip(got, exp, strict=True):
        assert g["related_ids"] == e["related_ids"]
        assert g["related_ids"] == sorted(g["related_ids"])


def test_standings_order_and_aggregates():
    """Standings order, ring_diff, and summary aggregates match the ruleset."""
    got = _load_report()
    exp = _expected_report()
    assert got["standings"] == exp["standings"]
    assert got["summary"] == exp["summary"]
    assert got["standings"][0]["rank"] == 1


def test_no_legacy_point_remap():
    """Wins award win_points and draws award draw_points, never legacy 2/0."""
    for m in _load_report()["matches"]:
        if m["winner"] == "A":
            assert m["points_a"] == 3 and m["points_b"] == 0
        elif m["winner"] == "B":
            assert m["points_a"] == 0 and m["points_b"] == 3
        else:
            assert m["points_a"] == 1 and m["points_b"] == 1


def test_reason_token_vocabulary():
    """Reason tokens and severity/score pairs follow the championship table."""
    allowed = {"ring_target", "ring_majority", "mutual_draw"}
    exp_by_id = {m["match_id"]: m for m in _expected_report()["matches"]}
    for m in _load_report()["matches"]:
        assert m["reason"] in allowed
        sev, sc = _score(m["reason"])
        assert m["severity"] == sev
        assert m["priority_score"] == sc
        assert m["reason"] == exp_by_id[m["match_id"]]["reason"]


def test_key_match_resolutions():
    """Spot-check matches that flip under legacy leave/flip/row/gate paths."""
    by_id = {m["match_id"]: m for m in _load_report()["matches"]}
    assert by_id["m01"]["winner"] == "A" and by_id["m01"]["reason"] == "ring_target"
    assert by_id["m01"]["rings_removed_a"] == 3
    assert by_id["m02"]["winner"] == "B" and by_id["m02"]["reason"] == "ring_target"
    assert by_id["m05"]["flips_a"] == 3 and by_id["m05"]["rings_removed_a"] == 2
    assert by_id["m06"]["rings_removed_a"] == 1
    assert by_id["m08"]["winner"] == "draw" and by_id["m08"]["reason"] == "mutual_draw"
