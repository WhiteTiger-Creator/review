"""Private verifier for Sky Kingdom Fleet Campaign."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
from pathlib import Path

from reference_campaign import reference_edge_cost, reference_paid_fuel

BIN = Path(os.environ.get("SKYKINGDOM_BIN", "/app/skykingdom/skykingdom"))
SCENARIO_DIR = Path(os.environ.get("SCENARIO_DIR", "/app/skykingdom/scenarios"))
SKY_DIR = Path(os.environ.get("SKYKINGDOM_DIR", "/app/skykingdom"))


def eval_op(payload: dict) -> dict:
    assert BIN.is_file(), f"missing binary {BIN}"
    proc = subprocess.run(
        [str(BIN), "eval"],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert proc.stderr == "", proc.stderr
    assert proc.stdout.strip(), "empty stdout"
    return json.loads(proc.stdout)


def must_ok(payload: dict):
    resp = eval_op(payload)
    assert resp.get("ok") is True, resp
    return resp["result"]


def load_scenario(name: str = "01_cirrus_opening.json") -> dict:
    return json.loads((SCENARIO_DIR / name).read_text())


def all_scenarios():
    return sorted(SCENARIO_DIR.glob("*.json"))


def digest(obj) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def test_agent_environment_contains_no_private_judge_material():
    """Environment must ship normative docs without private judge or solution trees."""
    forbidden = ["solution", "tests", "oracle", "expected", "reference_campaign"]
    for root, dirs, files in os.walk(SKY_DIR):
        names = set(dirs) | set(files)
        for bad in forbidden:
            assert bad not in names, (root, bad)
    # Normative docs present
    for doc in [
        "FLEET_RULES.md",
        "COMBAT_RULES.md",
        "WEATHER_SYSTEM.md",
        "SUPPLY_LOGISTICS.md",
        "TECHNOLOGY_TREE.md",
        "DIPLOMACY_RULES.md",
        "TERRITORY_CONTROL.md",
        "CAMPAIGN_RULES.md",
        "SCENARIO_SCHEMA.md",
        "API_SPEC.md",
    ]:
        assert (SKY_DIR / doc).is_file()


def test_hull_and_tech_catalog_order():
    """hullCatalog and techCatalog must match API_SPEC insertion order and SCOUT stats."""
    hulls = must_ok({"op": "hullCatalog"})
    assert [h["id"] for h in hulls] == ["SCOUT", "FRIGATE", "GALLEON", "FORTRESS"]
    assert hulls[0] == {
        "id": "SCOUT",
        "atk": 4,
        "def": 2,
        "fuel_cap": 6,
        "base_range": 3,
        "upkeep": 1,
    }
    techs = must_ok({"op": "techCatalog"})
    assert [t["id"] for t in techs] == [
        "LATTICE_SAILS",
        "AETHER_INJECTORS",
        "HARPOON_BALLISTA",
        "SKYIRON_PLATING",
        "STORMSEER_LENS",
        "CROWN_DOCKS",
    ]


def test_every_supplied_scenario_validates_and_creates():
    """Every public scenario must validate and create a running turn-1 campaign."""
    ids = []
    for path in all_scenarios():
        sc = json.loads(path.read_text())
        out = must_ok({"op": "validateScenario", "scenario": sc})
        assert out["id"] == sc["id"]
        game = must_ok({"op": "createGame", "scenario": sc})
        assert game["state"] == "running"
        assert game["turn"] == 1
        assert game["player"] == sc["player_kingdom"]
        ids.append(sc["id"])
    assert len(ids) == len(set(ids)) >= 8


def test_validate_scenario_rejects_disconnected_and_bad_weather():
    """Scenario validation must reject disconnected graphs and illegal weather ids."""
    sc = load_scenario()
    bad = copy.deepcopy(sc)
    # Two components: A1-D1 and B1-C1 with no bridge
    bad["edges"] = [{"a": "A1", "b": "D1"}, {"a": "B1", "b": "C1"}]
    resp = eval_op({"op": "validateScenario", "scenario": bad})
    assert resp["ok"] is False

    bad2 = copy.deepcopy(sc)
    bad2["weather_schedule"][0]["A1"] = "HURRICANE"
    resp = eval_op({"op": "validateScenario", "scenario": bad2})
    assert resp["ok"] is False


def test_validate_scenario_rejects_self_loop_and_duplicate_edges():
    """validateScenario must reject self-loops and duplicate undirected edge pairs."""
    sc = load_scenario()
    looped = copy.deepcopy(sc)
    looped["edges"] = list(sc["edges"]) + [{"a": "A1", "b": "A1"}]
    assert eval_op({"op": "validateScenario", "scenario": looped})["ok"] is False

    dup = copy.deepcopy(sc)
    dup["edges"] = list(sc["edges"]) + [{"a": "C1", "b": "A1"}]  # reverse of A1-C1
    assert eval_op({"op": "validateScenario", "scenario": dup})["ok"] is False


def test_validate_scenario_returns_independent_copy():
    """validateScenario must return a deep copy isolated from caller mutation."""
    sc = load_scenario()
    sc["name"] = "MUT"
    out = must_ok({"op": "validateScenario", "scenario": sc})
    sc["name"] = "CHANGED"
    assert out["name"] == "MUT"


def test_shortest_path_lex_tiebreak():
    """Equal-length routes must pick the lexicographically smallest island path."""
    sc = load_scenario()
    g = must_ok({"op": "createGame", "scenario": sc})
    # A1 to B1 has two length-2 paths: A1-C1-B1 and A1-D1-B1; lex smaller is A1,C1,B1
    res = must_ok({"op": "shortestPath", "game": g, "from": "A1", "to": "B1"})
    assert res["distance"] == 2
    assert res["path"] == ["A1", "C1", "B1"]


def test_path_fuel_cost_uses_destination_weather_ceil():
    """Path fuel raw cost must ceil destination weather multipliers then apply discounts."""
    sc = load_scenario()
    # Force known weather on C1 for turn 1
    sc["weather_schedule"][0] = {
        "A1": "CLEAR",
        "B1": "CLEAR",
        "C1": "STORM",
        "D1": "CLEAR",
    }
    g = must_ok({"op": "createGame", "scenario": sc})
    res = must_ok({"op": "pathFuelCost", "game": g, "fleet_id": "SF1", "to": "C1"})
    # STORM move_mul 200 -> ceil 2; captain logistics 3 => discount 15; paid = max(1, floor(2*85/100))=1
    assert res["raw_cost"] == 2
    assert res["paid"] == 1
    assert res["path"] == ["A1", "C1"]


def test_move_consumes_fuel_and_readiness_and_rejects_war_territory():
    """MOVE must reject WAR-owned destinations atomically and apply fuel/readiness on success."""
    sc = load_scenario()
    g = must_ok({"op": "createGame", "scenario": sc})
    before = copy.deepcopy(g)
    res = must_ok({"op": "executeCommand", "game": g, "line": "MOVE SF1 B1"})
    assert res["output"].startswith("Rejected command:")
    assert res["game"]["fleets"]["SF1"] == before["fleets"]["SF1"]
    assert res["game"]["history"] == []

    res = must_ok({"op": "executeCommand", "game": g, "line": "move SF1 C1"})
    assert res["output"] == "Moved"
    assert res["game"]["history"] == ["MOVE SF1 C1"]
    fleet = res["game"]["fleets"]["SF1"]
    assert fleet["island"] == "C1"
    assert fleet["readiness"] == 95
    assert fleet["fuel"] < before["fleets"]["SF1"]["fuel"]


def test_rejected_research_is_atomic():
    """Illegal RESEARCH must leave treasury, researched list, and history unchanged."""
    sc = load_scenario()
    g = must_ok({"op": "createGame", "scenario": sc})
    snap = digest(g)
    res = must_ok({"op": "executeCommand", "game": g, "line": "RESEARCH AETHER_INJECTORS"})
    assert res["output"].startswith("Rejected command:")
    assert digest(res["game"]) == snap


def test_research_prerequisite_chain_and_effects():
    """RESEARCH must enforce prerequisite chain LATTICE_SAILS before AETHER_INJECTORS."""
    sc = load_scenario()
    sc["kingdoms"][0]["aetherium"] = 80
    sc["kingdoms"][0]["crystal"] = 40
    g = must_ok({"op": "createGame", "scenario": sc})
    blocked = must_ok({"op": "executeCommand", "game": g, "line": "RESEARCH AETHER_INJECTORS"})
    assert blocked["output"].startswith("Rejected command:")
    g = must_ok({"op": "executeCommand", "game": g, "line": "RESEARCH LATTICE_SAILS"})["game"]
    assert "LATTICE_SAILS" in g["kingdoms"]["SKY"]["researched"]
    g = must_ok({"op": "executeCommand", "game": g, "line": "RESEARCH AETHER_INJECTORS"})["game"]
    assert "AETHER_INJECTORS" in g["kingdoms"]["SKY"]["researched"]


def test_treaty_transition_matrix():
    """TREATY must block illegal ALLIED-to-WAR jumps and allow EMBARGO bridge."""
    sc = load_scenario()
    sc["diplomacy"] = [{"kingdom_a": "SKY", "kingdom_b": "IRON", "stance": "PEACE"}]
    g = must_ok({"op": "createGame", "scenario": sc})
    # ALLIED -> WAR illegal
    g = must_ok({"op": "executeCommand", "game": g, "line": "TREATY IRON ALLIED"})["game"]
    res = must_ok({"op": "executeCommand", "game": g, "line": "TREATY IRON WAR"})
    assert res["output"].startswith("Rejected command:")
    g = must_ok({"op": "executeCommand", "game": g, "line": "TREATY IRON EMBARGO"})["game"]
    g = must_ok({"op": "executeCommand", "game": g, "line": "TREATY IRON WAR"})["game"]
    key = "IRON|SKY"
    assert g["diplomacy"][key] == "WAR"


def test_fortify_costs_timber():
    """FORTIFY must spend 8 timber and raise fortification by one."""
    sc = load_scenario()
    g = must_ok({"op": "createGame", "scenario": sc})
    timber = g["kingdoms"]["SKY"]["timber"]
    fort = g["islands"]["A1"]["fortification"]
    g = must_ok({"op": "executeCommand", "game": g, "line": "FORTIFY A1"})["game"]
    assert g["kingdoms"]["SKY"]["timber"] == timber - 8
    assert g["islands"]["A1"]["fortification"] == fort + 1


def test_supply_requires_owned_or_allied_path_to_depot():
    """isSupplied requires self/allied ownership path to an owned depot."""
    sc = load_scenario()
    g = must_ok({"op": "createGame", "scenario": sc})
    g = must_ok({"op": "executeCommand", "game": g, "line": "MOVE SF1 C1"})["game"]
    assert must_ok({"op": "isSupplied", "game": g, "fleet_id": "SF1"}) is False
    # claim C1 via fort-only? unowned — need clash from adjacent; move back and take via...
    # Own path: move to D1 (owned) should be supplied via A1 depot through D1-A1
    g2 = must_ok({"op": "createGame", "scenario": sc})
    g2 = must_ok({"op": "executeCommand", "game": g2, "line": "MOVE SF1 D1"})["game"]
    assert must_ok({"op": "isSupplied", "game": g2, "fleet_id": "SF1"}) is True


def test_combat_preview_matches_simulate_without_mutating_input():
    """combatPreview scores must match simulateClash without mutating the caller game."""
    sc = load_scenario()
    g = must_ok({"op": "createGame", "scenario": sc})
    g = must_ok({"op": "executeCommand", "game": g, "line": "MOVE SF1 C1"})["game"]
    before = digest(g)
    preview = must_ok({"op": "combatPreview", "game": g, "fleet_id": "SF1", "target": "B1"})
    assert digest(g) == before
    g2 = copy.deepcopy(g)
    sim = must_ok({"op": "simulateClash", "game": g2, "fleet_id": "SF1", "target": "B1"})
    assert sim["clash"]["attacker_score"] == preview["attacker_score"]
    assert sim["clash"]["defender_score"] == preview["defender_score"]
    assert digest(g2) == digest(g)


def test_clash_command_and_defender_advantage_on_tie_path():
    """CLASH must resolve with defender win when attacker is outmatched."""
    sc = load_scenario()
    # Make attacker weak
    sc["fleets"][0]["hulls"] = ["SCOUT"]
    sc["fleets"][0]["fuel"] = 6
    sc["fleets"][1]["hulls"] = ["FORTRESS", "FORTRESS"]
    sc["fleets"][1]["fuel"] = 24
    g = must_ok({"op": "createGame", "scenario": sc})
    g = must_ok({"op": "executeCommand", "game": g, "line": "MOVE SF1 C1"})["game"]
    g = must_ok({"op": "executeCommand", "game": g, "line": "CLASH SF1 B1"})["game"]
    assert g["last_clash"]["winner"] == "defender"


def test_status_render_exact_shape():
    """renderGame/STATUS text must match API_SPEC line layout."""
    sc = load_scenario()
    g = must_ok({"op": "createGame", "scenario": sc})
    text = must_ok({"op": "renderGame", "game": g})
    assert text.startswith("Turn 1 [running] Player=SKY\n")
    assert "Treasury aetherium=" in text
    assert text.endswith("Researched: (none)\n")


def test_endturn_economy_weather_and_score():
    """ENDTURN must advance turn, apply economy, and expose complete score breakdown."""
    sc = load_scenario()
    g = must_ok({"op": "createGame", "scenario": sc})
    fuel = g["kingdoms"]["SKY"]["fuel"]
    crystal = g["kingdoms"]["SKY"]["crystal"]
    weather_a1 = g["islands"]["A1"]["weather"]
    g = must_ok({"op": "executeCommand", "game": g, "line": "ENDTURN"})["game"]
    assert g["turn"] == 2
    # Depot income on A1 (3+level) increases treasury fuel; crystal yields accumulate.
    assert g["kingdoms"]["SKY"]["fuel"] > fuel
    assert g["kingdoms"]["SKY"]["crystal"] > crystal
    assert g["islands"]["A1"]["weather"] == sc["weather_schedule"][1]["A1"]
    assert g["islands"]["A1"]["weather"] != weather_a1 or sc["weather_schedule"][0]["A1"] == sc["weather_schedule"][1]["A1"]
    score = must_ok({"op": "scoreGame", "game": g})
    assert set(score) >= {
        "objective",
        "territory",
        "resources",
        "survival",
        "dominance",
        "violations",
        "mission",
        "total",
    }
    assert score["total"] == sum(score[k] for k in score if k != "total")


def test_replay_run_matches_sequential_execute():
    """replayRun must equal sequential executeCommand outputs and final state."""
    sc = load_scenario()
    commands = ["MOVE SF1 C1", "FORTIFY A1", "ENDTURN", "STATUS"]
    replay = must_ok({"op": "replayRun", "scenario": sc, "commands": commands})
    g = must_ok({"op": "createGame", "scenario": sc})
    outs = []
    for line in commands:
        res = must_ok({"op": "executeCommand", "game": g, "line": line})
        g = res["game"]
        outs.append(res["output"])
    assert outs == replay["outputs"]
    assert digest(g) == digest(replay["game"])


def test_reboot_restores_fresh_campaign_same_scenario():
    """REBOOT must restore initial fleet locations and clear history."""
    sc = load_scenario()
    g = must_ok({"op": "createGame", "scenario": sc})
    g = must_ok({"op": "executeCommand", "game": g, "line": "MOVE SF1 C1"})["game"]
    g = must_ok({"op": "executeCommand", "game": g, "line": "REBOOT"})["game"]
    assert g["turn"] == 1
    assert g["history"] == []
    assert g["fleets"]["SF1"]["island"] == "A1"


def test_cross_scenario_movement_combat_digest():
    """Cross-scenario clash/score digests must diversify so hardcoding fails."""
    digests = []
    for path in all_scenarios():
        sc = json.loads(path.read_text())
        # only WAR scenarios for clash probe
        if not sc["diplomacy"] or sc["diplomacy"][0]["stance"] != "WAR":
            g = must_ok({"op": "createGame", "scenario": sc})
            digests.append(digest(must_ok({"op": "scoreGame", "game": g})))
            continue
        result = must_ok(
            {
                "op": "replayRun",
                "scenario": sc,
                "commands": ["MOVE SF1 C1", "CLASH SF1 B1", "ENDTURN"],
            }
        )
        digests.append(digest({"clash": result["game"].get("last_clash"), "score": must_ok({"op": "scoreGame", "game": result["game"]})}))
    assert len(set(digests)) >= 5
    # stable aggregate fingerprint (engine regression guard)
    assert digest(digests)[:16] != "0" * 16


def test_validate_game_flags_overfuel_when_corrupted():
    """validateGame must flag fleets whose fuel exceeds hull capacity."""
    sc = load_scenario()
    g = must_ok({"op": "createGame", "scenario": sc})
    g["fleets"]["SF1"]["fuel"] = 999
    res = must_ok({"op": "validateGame", "game": g})
    assert res["legal"] is False
    assert any(v.startswith("fuel:") for v in res["violations"])


def test_play_cli_exit():
    """play mode must print STATUS and honor EXIT."""
    sc_path = SCENARIO_DIR / "01_cirrus_opening.json"
    proc = subprocess.run(
        [str(BIN), "play", str(sc_path)],
        input="STATUS\nEXIT\n",
        text=True,
        capture_output=True,
        timeout=20,
        check=True,
    )
    assert "Turn 1 [running]" in proc.stdout
    assert "Exiting" in proc.stdout


def test_hidden_fixture_crystal_victory_path():
    """Hidden crystal fixture mission points must track crystal/5 after ENDTURNs."""
    fixture = Path(__file__).parent / "verifier-fixtures" / "crystal_pressure.json"
    sc = json.loads(fixture.read_text())
    must_ok({"op": "validateScenario", "scenario": sc})
    result = must_ok(
        {
            "op": "replayRun",
            "scenario": sc,
            "commands": [
                "RESEARCH HARPOON_BALLISTA",
                "ENDTURN",
                "ENDTURN",
                "ENDTURN",
                "ENDTURN",
                "ENDTURN",
            ],
        }
    )
    # crystal accumulates from yields; score mission uses crystal/5
    score = must_ok({"op": "scoreGame", "game": result["game"]})
    assert score["mission"] == result["game"]["kingdoms"]["SKY"]["crystal"] // 5


def test_hidden_fixture_lex_path_and_storm_fuel():
    """Hidden storm bridge fixture must keep N1-N2-N4 lex path and STORM fuel cost 2."""
    fixture = Path(__file__).parent / "verifier-fixtures" / "storm_lex_bridge.json"
    sc = json.loads(fixture.read_text())
    g = must_ok({"op": "createGame", "scenario": sc})
    path = must_ok({"op": "shortestPath", "game": g, "from": "N1", "to": "N4"})
    assert path["path"] == ["N1", "N2", "N4"]
    fuel = must_ok({"op": "pathFuelCost", "game": g, "fleet_id": "F1", "to": "N2"})
    assert fuel["raw_cost"] == 2  # STORM on N2
    assert fuel["raw_cost"] == reference_edge_cost("STORM")
    assert fuel["paid"] == reference_paid_fuel(fuel["raw_cost"], 0)


def test_history_staging_snapshot_survives_rejected_ingest():
    """Successful MOVE stages history; rejected follow-up must snapshot-preserve staged history."""
    sc = load_scenario()
    g = must_ok({"op": "createGame", "scenario": sc})
    g = must_ok({"op": "executeCommand", "game": g, "line": "MOVE SF1 C1"})["game"]
    staged = list(g["history"])
    assert staged == ["MOVE SF1 C1"]
    snap = digest(g)
    rejected = must_ok({"op": "executeCommand", "game": g, "line": "MOVE SF1 B1"})
    assert rejected["output"].startswith("Rejected command:")
    assert rejected["game"]["history"] == staged
    assert digest(rejected["game"]) == snap


def test_ingest_scenario_export_score_roundtrip():
    """Ingest via createGame then export scoreGame must be stable for an unchanged staging snapshot."""
    sc = load_scenario()
    g = must_ok({"op": "createGame", "scenario": sc})
    export1 = must_ok({"op": "scoreGame", "game": g})
    export2 = must_ok({"op": "scoreGame", "game": g})
    assert export1 == export2
    assert export1["territory"] == 5 * sum(
        1 for isl in g["islands"].values() if isl["owner"] == g["player"]
    )


def test_refuel_rejects_non_depot_and_restores_on_owned_depot():
    """REFUEL must reject off-depot islands and fully restore fuel/readiness on an owned depot."""
    sc = load_scenario()
    g = must_ok({"op": "createGame", "scenario": sc})
    g = must_ok({"op": "executeCommand", "game": g, "line": "MOVE SF1 C1"})["game"]
    rejected = must_ok({"op": "executeCommand", "game": g, "line": "REFUEL SF1"})
    assert rejected["output"].startswith("Rejected command:")
    assert rejected["game"]["fleets"]["SF1"]["fuel"] == g["fleets"]["SF1"]["fuel"]
    g = must_ok({"op": "executeCommand", "game": g, "line": "MOVE SF1 A1"})["game"]
    before_fuel = g["fleets"]["SF1"]["fuel"]
    assert before_fuel < 16
    res = must_ok({"op": "executeCommand", "game": g, "line": "REFUEL SF1"})
    assert res["output"] == "Refueled"
    assert res["game"]["fleets"]["SF1"]["fuel"] == 16
    assert res["game"]["fleets"]["SF1"]["readiness"] == 100
    assert res["game"]["history"][-1] == "REFUEL SF1"


def test_npc_doctrine_prefers_adjacent_clash_on_endturn():
    """ENDTURN NPC must clash the lex-smallest legal adjacent target, including unowned islands hosting WAR fleets."""
    sc = load_scenario()
    g = must_ok({"op": "createGame", "scenario": sc})
    g = must_ok({"op": "executeCommand", "game": g, "line": "MOVE SF1 C1"})["game"]
    g = must_ok({"op": "executeCommand", "game": g, "line": "ENDTURN"})["game"]
    clash = g.get("last_clash")
    assert clash is not None
    assert clash["attacker_id"] == "IF1"
    assert clash["island_id"] == "C1"
    assert clash["defender_id"] == "SF1"


def test_create_game_uses_id_keyed_maps_not_arrays():
    """createGame must expose kingdoms/islands/fleets/captains/diplomacy as id-keyed objects with field player."""
    sc = load_scenario()
    g = must_ok({"op": "createGame", "scenario": sc})
    assert isinstance(g["fleets"], dict)
    assert isinstance(g["kingdoms"], dict)
    assert isinstance(g["islands"], dict)
    assert isinstance(g["captains"], dict)
    assert isinstance(g["diplomacy"], dict)
    assert "SF1" in g["fleets"]
    assert g["player"] == "SKY"
    assert "player_kingdom" not in g


def test_map_fleet_island_exact_renders():
    """MAP, FLEET, and ISLAND must match API_SPEC render lines and leave history unchanged."""
    sc = load_scenario()
    g = must_ok({"op": "createGame", "scenario": sc})
    mapped = must_ok({"op": "executeCommand", "game": g, "line": "MAP"})
    assert mapped["game"]["history"] == []
    lines = mapped["output"].splitlines()
    assert lines[0].startswith("A1 owner=SKY fort=")
    assert "weather=" in lines[0] and "depot=true" in lines[0]
    assert any(line.startswith("B1 owner=IRON") for line in lines)
    fleet = must_ok({"op": "executeCommand", "game": g, "line": "FLEET SF1"})
    assert fleet["output"] == "SF1 kingdom=SKY island=A1 fuel=12 readiness=100 hulls=FRIGATE,SCOUT captain=CAP_SKY\n"
    island = must_ok({"op": "executeCommand", "game": g, "line": "ISLAND A1"})
    assert island["output"].startswith("A1 owner=SKY fort=1 weather=")
    assert "depot=true level=2\n" in island["output"]
    bad = must_ok({"op": "executeCommand", "game": g, "line": "FLEET NOPE"})
    assert bad["output"].startswith("Rejected command:")


def test_command_verb_case_insensitivity_mixed():
    """Command verbs must accept mixed case while preserving case-sensitive IDs."""
    sc = load_scenario()
    g = must_ok({"op": "createGame", "scenario": sc})
    for verb in ("Move", "mOvE"):
        g = must_ok({"op": "executeCommand", "game": g, "line": "REBOOT"})["game"]
        res = must_ok({"op": "executeCommand", "game": g, "line": f"{verb} SF1 C1"})
        assert res["output"] == "Moved"
        assert res["game"]["history"] == ["MOVE SF1 C1"]


def test_hidden_npc_prefers_unowned_war_fleet_over_owned_war_lex_larger():
    """Hidden fixture: NPC must prefer lex-smaller unowned island with WAR fleet over lex-larger owned WAR island."""
    fixture = Path(__file__).parent / "verifier-fixtures" / "npc_lex_clash.json"
    sc = json.loads(fixture.read_text())
    result = must_ok(
        {
            "op": "replayRun",
            "scenario": sc,
            "commands": ["MOVE PF1 X1", "ENDTURN"],
        }
    )
    clash = result["game"]["last_clash"]
    assert clash is not None
    assert clash["attacker_id"] == "EF1"
    assert clash["island_id"] == "X1"
    assert clash["defender_id"] == "PF1"


def test_endturn_unsupplied_readiness_penalty():
    """ENDTURN must apply the unsupplied readiness -10 after upkeep when fleet cannot reach an owned/allied depot path."""
    sc = copy.deepcopy(load_scenario())
    # Keep NPC peaceful so ENDTURN does not CLASH the stranded fleet mid-assertion.
    sc["diplomacy"] = [{"kingdom_a": "SKY", "kingdom_b": "IRON", "stance": "PEACE"}]
    g = must_ok({"op": "createGame", "scenario": sc})
    g = must_ok({"op": "executeCommand", "game": g, "line": "MOVE SF1 C1"})["game"]
    assert g["fleets"]["SF1"]["island"] == "C1"
    assert g["fleets"]["SF1"]["readiness"] == 95
    assert must_ok({"op": "isSupplied", "game": g, "fleet_id": "SF1"}) is False
    before = g["fleets"]["SF1"]["readiness"]
    g = must_ok({"op": "executeCommand", "game": g, "line": "ENDTURN"})["game"]
    # upkeep succeeds (treasury has aetherium) so no -15; unsupplied applies -10
    assert g["fleets"]["SF1"]["readiness"] == before - 10


def test_move_rejects_fourth_fleet_stack():
    """MOVE must reject placing a fourth same-kingdom fleet on one island (FLEET_RULES stacking)."""
    fixture = Path(__file__).parent / "verifier-fixtures" / "stack_pressure.json"
    sc = json.loads(fixture.read_text())
    g = must_ok({"op": "createGame", "scenario": sc})
    before = digest(g)
    res = must_ok({"op": "executeCommand", "game": g, "line": "MOVE SF4 A1"})
    assert res["output"].startswith("Rejected command:")
    assert digest(res["game"]) == before
    assert res["game"]["fleets"]["SF4"]["island"] == "D1"


def test_terminal_won_rejects_mutating_commands():
    """Crystal victory must set state won and reject mutating commands except REBOOT."""
    fixture = Path(__file__).parent / "verifier-fixtures" / "quick_crystal_win.json"
    sc = json.loads(fixture.read_text())
    # 10 + 7*2 = 24 crystal after two ENDTURNs
    result = must_ok(
        {
            "op": "replayRun",
            "scenario": sc,
            "commands": ["ENDTURN", "ENDTURN"],
        }
    )
    g = result["game"]
    assert g["state"] == "won"
    assert g["kingdoms"]["SKY"]["crystal"] >= 24
    assert g["score_breakdown"] is not None
    assert g["score_breakdown"]["objective"] == 100
    rejected = must_ok({"op": "executeCommand", "game": g, "line": "FORTIFY A1"})
    assert rejected["output"].startswith("Rejected command:")
    assert rejected["game"]["state"] == "won"
    assert rejected["game"]["kingdoms"]["SKY"]["timber"] == g["kingdoms"]["SKY"]["timber"]
    status = must_ok({"op": "executeCommand", "game": g, "line": "STATUS"})
    assert "[won]" in status["output"]
    rebooted = must_ok({"op": "executeCommand", "game": g, "line": "REBOOT"})
    assert rebooted["game"]["state"] == "running"
    assert rebooted["game"]["history"] == []
