from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import subprocess
from pathlib import Path

import pytest

APP = Path(os.environ.get("APP_ROOT", "/app"))
BUILD = APP / "bin" / "build-tidefront"
CLI = APP / "bin" / "tidefront"


def run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


@pytest.fixture(scope="session", autouse=True)
def build_product() -> None:
    proc = run([str(BUILD)], env={**os.environ, "APP_ROOT": str(APP)})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (APP / "dist/bin/tidefront").is_file()


def compact(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode()


def base_players() -> list[dict[str, object]]:
    return [
        {"id": "amber", "initiative": 2},
        {"id": "cobalt", "initiative": 1},
    ]


def base_nodes() -> list[dict[str, object]]:
    return [
        {
            "id": "A",
            "station_id": "station-A",
            "base_depth_m": 1.0,
            "value": 3,
            "owner": "amber",
        },
        {
            "id": "B",
            "station_id": "station-B",
            "base_depth_m": 1.0,
            "value": 4,
        },
        {
            "id": "C",
            "station_id": "station-C",
            "base_depth_m": 1.0,
            "value": 5,
            "owner": "cobalt",
        },
        {
            "id": "D",
            "station_id": "station-D",
            "base_depth_m": 1.0,
            "value": 2,
        },
    ]


def base_edges() -> list[dict[str, str]]:
    return [
        {"a": "A", "b": "B"},
        {"a": "B", "b": "C"},
        {"a": "C", "b": "D"},
        {"a": "D", "b": "A"},
    ]


def base_fleets() -> list[dict[str, object]]:
    return [
        {"id": "amber-1", "player_id": "amber", "node_id": "A", "draft_m": 1.0},
        {"id": "cobalt-1", "player_id": "cobalt", "node_id": "C", "draft_m": 1.0},
    ]


def make_match(
    *,
    match_id: str = "case",
    players: list[dict[str, object]] | None = None,
    nodes: list[dict[str, object]] | None = None,
    edges: list[dict[str, str]] | None = None,
    fleets: list[dict[str, object]] | None = None,
    orders: list[dict[str, object]] | None = None,
    start_utc: str = "2016-12-31T23:59:59Z",
    turn_seconds: int = 1,
    turn_count: int = 1,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "match_id": match_id,
        "start_utc": start_utc,
        "turn_seconds": turn_seconds,
        "turn_count": turn_count,
        "players": players if players is not None else base_players(),
        "nodes": nodes if nodes is not None else base_nodes(),
        "edges": edges if edges is not None else base_edges(),
        "fleets": fleets if fleets is not None else base_fleets(),
        "orders": orders if orders is not None else [],
    }


def write_case(
    root: Path,
    match: dict[str, object],
    *,
    tides: dict[str, float] | None = None,
) -> tuple[Path, Path, Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    match_path = root / "match.json"
    stations_path = root / "stations.json"
    catalog_dir = root / "catalog"
    leaps_path = root / "leaps.txt"
    match_path.write_bytes(compact(match) + b"\n")
    catalog_dir.mkdir()
    shutil.copy2(APP / "examples/game/catalog/M2.json", catalog_dir / "M2.json")
    shutil.copy2(APP / "examples/game/leaps.txt", leaps_path)
    selected_tides = tides or {}
    station_ids = sorted({str(node["station_id"]) for node in match["nodes"]})
    stations = []
    for station_id in station_ids:
        stations.append(
            {
                "id": station_id,
                "latitude_deg": 0,
                "longitude_deg": 0,
                "overrides": {"datum_m": selected_tides.get(station_id, 0.0)},
                "constituents": [
                    {
                        "name": "M2",
                        "amplitude_m": 0,
                        "phase_deg": 0,
                        "required": True,
                    }
                ],
            }
        )
    stations_path.write_bytes(
        compact({"schema_version": 1, "stations": stations}) + b"\n"
    )
    return match_path, stations_path, catalog_dir, leaps_path


def command(
    match: Path,
    stations: Path,
    catalog: Path,
    leaps: Path,
    output: Path,
    *,
    threads: int = 2,
) -> list[str]:
    return [
        str(CLI),
        "adjudicate",
        "--match",
        str(match.resolve()),
        "--stations",
        str(stations.resolve()),
        "--catalog",
        str(catalog.resolve()),
        "--leaps",
        str(leaps.resolve()),
        "--threads",
        str(threads),
        "--output",
        str(output.resolve()),
    ]


def run_case(
    tmp_path: Path,
    match: dict[str, object],
    *,
    tides: dict[str, float] | None = None,
    threads: int = 2,
    cwd: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, dict[str, object] | None]:
    paths = write_case(tmp_path / "inputs", match, tides=tides)
    output = tmp_path / "result.json"
    proc = run(command(*paths, output, threads=threads), cwd=cwd)
    payload = json.loads(output.read_text()) if output.exists() else None
    return proc, output, payload


def fleet_row(payload: dict[str, object], fleet_id: str, turn: int = 1) -> dict[str, object]:
    rows = payload["turns"][turn - 1]["fleets"]
    return next(row for row in rows if row["id"] == fleet_id)


def score_map(rows: list[dict[str, object]]) -> dict[str, int]:
    return {str(row["player_id"]): int(row["points"]) for row in rows}


def expected_digest(payload: dict[str, object]) -> str:
    records: list[str] = []
    for turn in payload["turns"]:
        records.append(f"T\t{turn['turn']}\t{turn['utc']}\n")
        for node in turn["nodes"]:
            records.append(
                "N\t{}\t{:.6f}\t{:.6f}\t{}\n".format(
                    node["id"],
                    node["tide_m"],
                    node["effective_depth_m"],
                    node.get("owner", ""),
                )
            )
        for fleet in turn["fleets"]:
            records.append(
                f"F\t{fleet['id']}\t{fleet['node_id']}\t{fleet['status']}\n"
            )
        for score in turn["scores"]:
            records.append(f"S\t{score['player_id']}\t{score['points']}\n")
    return hashlib.sha256("".join(records).encode()).hexdigest()


def assert_failure_without_output(
    tmp_path: Path,
    match: dict[str, object],
    *,
    tides: dict[str, float] | None = None,
) -> subprocess.CompletedProcess[str]:
    paths = write_case(tmp_path / "inputs", match, tides=tides)
    output = tmp_path / "result.json"
    output.write_text("stale", encoding="utf-8")
    proc = run(command(*paths, output))
    assert proc.returncode != 0
    assert proc.stdout == ""
    assert not output.exists()
    return proc


def test_bundled_game_resolves_and_writes_result(tmp_path: Path) -> None:
    output = tmp_path / "game.json"
    proc = run(
        command(
            APP / "examples/game/match.json",
            APP / "examples/game/stations.json",
            APP / "examples/game/catalog",
            APP / "examples/game/leaps.txt",
            output,
        )
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(output.read_text())
    assert payload["game"] == "tidefront-v1"
    assert payload["match_id"] == "demo-regatta"
    assert len(payload["turns"]) == 3
    assert proc.stdout == ""


def test_missing_order_is_hold(tmp_path: Path) -> None:
    proc, _, payload = run_case(tmp_path, make_match())
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-1")["status"] == "hold"
    assert fleet_row(payload, "cobalt-1")["status"] == "hold"


def test_explicit_hold_is_preserved(tmp_path: Path) -> None:
    orders = [{"turn": 1, "fleet_id": "amber-1", "kind": "hold"}]
    proc, _, payload = run_case(tmp_path, make_match(orders=orders))
    assert proc.returncode == 0, proc.stderr
    row = fleet_row(payload, "amber-1")
    assert row == {
        "id": "amber-1",
        "player_id": "amber",
        "node_id": "A",
        "order": "hold",
        "status": "hold",
    }


def test_move_at_exact_depth_boundary_succeeds(tmp_path: Path) -> None:
    orders = [
        {"turn": 1, "fleet_id": "amber-1", "kind": "move", "target_node_id": "B"}
    ]
    nodes = base_nodes()
    nodes[0]["base_depth_m"] = 0.6
    nodes[1]["base_depth_m"] = 0.8
    tides = {"station-A": 0.4, "station-B": 0.2}
    proc, _, payload = run_case(tmp_path, make_match(nodes=nodes, orders=orders), tides=tides)
    assert proc.returncode == 0, proc.stderr
    row = fleet_row(payload, "amber-1")
    assert row["status"] == "moved"
    assert row["node_id"] == "B"


@pytest.mark.parametrize("shallow_node", ["A", "B"])
def test_shallow_source_or_target_blocks_move(tmp_path: Path, shallow_node: str) -> None:
    orders = [
        {"turn": 1, "fleet_id": "amber-1", "kind": "move", "target_node_id": "B"}
    ]
    nodes = base_nodes()
    for node in nodes:
        if node["id"] == shallow_node:
            node["base_depth_m"] = 0.99
    proc, _, payload = run_case(tmp_path, make_match(nodes=nodes, orders=orders))
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-1")["status"] == "blocked-depth"


def test_nonadjacent_move_is_blocked_edge(tmp_path: Path) -> None:
    orders = [
        {"turn": 1, "fleet_id": "amber-1", "kind": "move", "target_node_id": "C"}
    ]
    proc, _, payload = run_case(tmp_path, make_match(orders=orders))
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-1")["status"] == "blocked-edge"


def test_same_target_contest_uses_higher_initiative(tmp_path: Path) -> None:
    orders = [
        {"turn": 1, "fleet_id": "amber-1", "kind": "move", "target_node_id": "B"},
        {"turn": 1, "fleet_id": "cobalt-1", "kind": "move", "target_node_id": "B"},
    ]
    proc, _, payload = run_case(tmp_path, make_match(orders=orders))
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-1")["status"] == "moved"
    assert fleet_row(payload, "cobalt-1")["status"] == "blocked-contest"


def test_contest_ties_use_player_then_fleet_id(tmp_path: Path) -> None:
    players = [
        {"id": "alpha", "initiative": 1},
        {"id": "beta", "initiative": 1},
    ]
    nodes = base_nodes()
    nodes[0]["owner"] = "alpha"
    nodes[2]["owner"] = "beta"
    fleets = [
        {"id": "zeta", "player_id": "alpha", "node_id": "A", "draft_m": 1.0},
        {"id": "aardvark", "player_id": "beta", "node_id": "C", "draft_m": 1.0},
    ]
    orders = [
        {"turn": 1, "fleet_id": "zeta", "kind": "move", "target_node_id": "B"},
        {"turn": 1, "fleet_id": "aardvark", "kind": "move", "target_node_id": "B"},
    ]
    proc, _, payload = run_case(
        tmp_path,
        make_match(players=players, nodes=nodes, fleets=fleets, orders=orders),
    )
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "zeta")["status"] == "moved"
    assert fleet_row(payload, "aardvark")["status"] == "blocked-contest"


def test_two_way_swap_succeeds_simultaneously(tmp_path: Path) -> None:
    fleets = [
        {"id": "amber-1", "player_id": "amber", "node_id": "A", "draft_m": 1.0},
        {"id": "cobalt-1", "player_id": "cobalt", "node_id": "B", "draft_m": 1.0},
    ]
    orders = [
        {"turn": 1, "fleet_id": "amber-1", "kind": "move", "target_node_id": "B"},
        {"turn": 1, "fleet_id": "cobalt-1", "kind": "move", "target_node_id": "A"},
    ]
    proc, _, payload = run_case(tmp_path, make_match(fleets=fleets, orders=orders))
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-1")["node_id"] == "B"
    assert fleet_row(payload, "cobalt-1")["node_id"] == "A"
    assert fleet_row(payload, "amber-1")["status"] == "moved"
    assert fleet_row(payload, "cobalt-1")["status"] == "moved"


def test_three_fleet_cycle_succeeds(tmp_path: Path) -> None:
    players = base_players() + [{"id": "jade", "initiative": 0}]
    nodes = base_nodes()[:3]
    edges = [{"a": "A", "b": "B"}, {"a": "B", "b": "C"}, {"a": "C", "b": "A"}]
    fleets = [
        {"id": "fa", "player_id": "amber", "node_id": "A", "draft_m": 1.0},
        {"id": "fb", "player_id": "cobalt", "node_id": "B", "draft_m": 1.0},
        {"id": "fc", "player_id": "jade", "node_id": "C", "draft_m": 1.0},
    ]
    orders = [
        {"turn": 1, "fleet_id": "fa", "kind": "move", "target_node_id": "B"},
        {"turn": 1, "fleet_id": "fb", "kind": "move", "target_node_id": "C"},
        {"turn": 1, "fleet_id": "fc", "kind": "move", "target_node_id": "A"},
    ]
    proc, _, payload = run_case(
        tmp_path,
        make_match(players=players, nodes=nodes, edges=edges, fleets=fleets, orders=orders),
    )
    assert proc.returncode == 0, proc.stderr
    assert {fleet_row(payload, fleet)["status"] for fleet in ["fa", "fb", "fc"]} == {"moved"}


def test_chain_into_empty_node_succeeds(tmp_path: Path) -> None:
    fleets = [
        {"id": "amber-1", "player_id": "amber", "node_id": "A", "draft_m": 1.0},
        {"id": "cobalt-1", "player_id": "cobalt", "node_id": "B", "draft_m": 1.0},
    ]
    orders = [
        {"turn": 1, "fleet_id": "amber-1", "kind": "move", "target_node_id": "B"},
        {"turn": 1, "fleet_id": "cobalt-1", "kind": "move", "target_node_id": "C"},
    ]
    proc, _, payload = run_case(tmp_path, make_match(fleets=fleets, orders=orders))
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-1")["node_id"] == "B"
    assert fleet_row(payload, "cobalt-1")["node_id"] == "C"


def test_chain_ending_at_stationary_fleet_is_blocked(tmp_path: Path) -> None:
    fleets = [
        {"id": "fa", "player_id": "amber", "node_id": "A", "draft_m": 1.0},
        {"id": "fb", "player_id": "cobalt", "node_id": "B", "draft_m": 1.0},
        {"id": "fc", "player_id": "cobalt", "node_id": "C", "draft_m": 1.0},
    ]
    orders = [
        {"turn": 1, "fleet_id": "fa", "kind": "move", "target_node_id": "B"},
        {"turn": 1, "fleet_id": "fb", "kind": "move", "target_node_id": "C"},
    ]
    proc, _, payload = run_case(tmp_path, make_match(fleets=fleets, orders=orders))
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "fa")["status"] == "blocked-occupied"
    assert fleet_row(payload, "fb")["status"] == "blocked-occupied"


def test_contest_loser_can_break_dependency_chain(tmp_path: Path) -> None:
    players = base_players() + [{"id": "jade", "initiative": 0}]
    fleets = [
        {"id": "fa", "player_id": "amber", "node_id": "A", "draft_m": 1.0},
        {"id": "fb", "player_id": "cobalt", "node_id": "B", "draft_m": 1.0},
        {"id": "fc", "player_id": "jade", "node_id": "C", "draft_m": 1.0},
    ]
    orders = [
        {"turn": 1, "fleet_id": "fa", "kind": "move", "target_node_id": "B"},
        {"turn": 1, "fleet_id": "fb", "kind": "move", "target_node_id": "C"},
        {"turn": 1, "fleet_id": "fc", "kind": "move", "target_node_id": "B"},
    ]
    proc, _, payload = run_case(
        tmp_path,
        make_match(players=players, fleets=fleets, orders=orders),
    )
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "fc")["status"] == "blocked-contest"
    assert fleet_row(payload, "fb")["status"] == "blocked-occupied"
    assert fleet_row(payload, "fa")["status"] == "blocked-occupied"


def test_capture_changes_owner_and_scores_node_values(tmp_path: Path) -> None:
    orders = [
        {"turn": 1, "fleet_id": "amber-1", "kind": "move", "target_node_id": "B"}
    ]
    proc, _, payload = run_case(tmp_path, make_match(orders=orders))
    assert proc.returncode == 0, proc.stderr
    owners = {node["id"]: node.get("owner", "") for node in payload["turns"][0]["nodes"]}
    assert owners["B"] == "amber"
    assert score_map(payload["turns"][0]["score_delta"]) == {"amber": 7, "cobalt": 5}


def test_scores_accumulate_across_turns(tmp_path: Path) -> None:
    orders = [
        {"turn": 1, "fleet_id": "amber-1", "kind": "move", "target_node_id": "B"},
        {"turn": 2, "fleet_id": "amber-1", "kind": "move", "target_node_id": "C"},
        {"turn": 2, "fleet_id": "cobalt-1", "kind": "move", "target_node_id": "D"},
    ]
    proc, _, payload = run_case(tmp_path, make_match(orders=orders, turn_count=2))
    assert proc.returncode == 0, proc.stderr
    first = score_map(payload["turns"][0]["scores"])
    second = score_map(payload["turns"][1]["scores"])
    assert first == {"amber": 7, "cobalt": 5}
    assert second == {"amber": 19, "cobalt": 7}


def test_winner_tie_breaks_by_initiative_then_player_id(tmp_path: Path) -> None:
    players = [
        {"id": "zulu", "initiative": 1},
        {"id": "alpha", "initiative": 2},
    ]
    nodes = base_nodes()[:2]
    nodes[0]["owner"] = "zulu"
    nodes[1]["owner"] = "alpha"
    nodes[0]["value"] = 3
    nodes[1]["value"] = 3
    fleets = [
        {"id": "fz", "player_id": "zulu", "node_id": "A", "draft_m": 1.0},
        {"id": "fa", "player_id": "alpha", "node_id": "B", "draft_m": 1.0},
    ]
    proc, _, payload = run_case(
        tmp_path,
        make_match(players=players, nodes=nodes, edges=[{"a": "A", "b": "B"}], fleets=fleets),
    )
    assert proc.returncode == 0, proc.stderr
    assert payload["final"]["winner"] == "alpha"


def test_declared_leap_second_is_a_distinct_turn(tmp_path: Path) -> None:
    proc, _, payload = run_case(tmp_path, make_match(turn_count=4))
    assert proc.returncode == 0, proc.stderr
    assert [turn["utc"] for turn in payload["turns"]] == [
        "2016-12-31T23:59:59Z",
        "2016-12-31T23:59:60Z",
        "2017-01-01T00:00:00Z",
        "2017-01-01T00:00:01Z",
    ]


def test_tide_and_effective_depth_round_to_six_decimals(tmp_path: Path) -> None:
    tides = {"station-A": 0.1234565}
    proc, _, payload = run_case(tmp_path, make_match(), tides=tides)
    assert proc.returncode == 0, proc.stderr
    node = next(row for row in payload["turns"][0]["nodes"] if row["id"] == "A")
    assert node["tide_m"] == 0.123456
    assert node["effective_depth_m"] == 1.123456


def test_output_arrays_are_sorted_independent_of_input_order(tmp_path: Path) -> None:
    match = make_match(
        players=list(reversed(base_players())),
        nodes=list(reversed(base_nodes())),
        edges=list(reversed(base_edges())),
        fleets=list(reversed(base_fleets())),
    )
    proc, _, payload = run_case(tmp_path, match)
    assert proc.returncode == 0, proc.stderr
    turn = payload["turns"][0]
    assert [row["id"] for row in turn["nodes"]] == ["A", "B", "C", "D"]
    assert [row["id"] for row in turn["fleets"]] == ["amber-1", "cobalt-1"]
    assert [row["player_id"] for row in turn["scores"]] == ["amber", "cobalt"]


def test_summary_digest_matches_documented_records(tmp_path: Path) -> None:
    proc, _, payload = run_case(tmp_path, make_match(turn_count=2))
    assert proc.returncode == 0, proc.stderr
    assert payload["summary"] == {
        "turn_count": 2,
        "fleet_count": 2,
        "sha256": expected_digest(payload),
    }


def test_compact_json_field_order_and_single_newline(tmp_path: Path) -> None:
    proc, output, payload = run_case(tmp_path, make_match())
    assert proc.returncode == 0, proc.stderr
    raw = output.read_bytes()
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
    assert b"\n" not in raw[:-1]
    assert list(payload) == ["schema_version", "game", "match_id", "turns", "final", "summary"]


def test_results_are_identical_across_threads_and_working_directories(tmp_path: Path) -> None:
    match = make_match(turn_count=3)
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    proc_a, out_a, _ = run_case(first_dir, match, threads=1, cwd=first_dir)
    proc_b, out_b, _ = run_case(second_dir, match, threads=8, cwd=second_dir)
    assert proc_a.returncode == 0, proc_a.stderr
    assert proc_b.returncode == 0, proc_b.stderr
    assert out_a.read_bytes() == out_b.read_bytes()


def test_repeat_runs_are_byte_identical(tmp_path: Path) -> None:
    paths = write_case(tmp_path / "inputs", make_match(turn_count=2))
    output = tmp_path / "result.json"
    first = run(command(*paths, output))
    assert first.returncode == 0, first.stderr
    original = output.read_bytes()
    second = run(command(*paths, output))
    assert second.returncode == 0, second.stderr
    assert output.read_bytes() == original


def test_dynamic_variants_defeat_fixture_hardcoding(tmp_path: Path) -> None:
    rng = random.Random(92017)
    digests = []
    for index in range(2):
        suffix = rng.randrange(1000, 9999)
        players = [
            {"id": f"p-{index}-a", "initiative": rng.randrange(2, 9)},
            {"id": f"p-{index}-b", "initiative": 1},
        ]
        nodes = [
            {
                "id": f"port-{suffix}-a",
                "station_id": f"station-{suffix}-a",
                "base_depth_m": 2.0,
                "value": 2 + index,
            },
            {
                "id": f"port-{suffix}-b",
                "station_id": f"station-{suffix}-b",
                "base_depth_m": 2.0,
                "value": 7 + index,
            },
        ]
        fleets = [
            {
                "id": f"fleet-{suffix}",
                "player_id": players[0]["id"],
                "node_id": nodes[0]["id"],
                "draft_m": 1.0,
            }
        ]
        orders = [
            {
                "turn": 1,
                "fleet_id": fleets[0]["id"],
                "kind": "move",
                "target_node_id": nodes[1]["id"],
            }
        ]
        match = make_match(
            match_id=f"generated-{suffix}",
            players=players,
            nodes=nodes,
            edges=[{"a": nodes[0]["id"], "b": nodes[1]["id"]}],
            fleets=fleets,
            orders=orders,
        )
        proc, _, payload = run_case(tmp_path / f"case-{index}", match)
        assert proc.returncode == 0, proc.stderr
        assert payload["match_id"] == f"generated-{suffix}"
        assert fleet_row(payload, fleets[0]["id"])["node_id"] == nodes[1]["id"]
        digests.append(payload["summary"]["sha256"])
    assert digests[0] != digests[1]


@pytest.mark.parametrize("mutation", ["unknown", "duplicate", "trailing"])
def test_match_json_is_strict_and_fail_closed(tmp_path: Path, mutation: str) -> None:
    match = make_match()
    paths = write_case(tmp_path / "inputs", match)
    match_path = paths[0]
    if mutation == "unknown":
        match["unexpected"] = True
        match_path.write_bytes(compact(match) + b"\n")
    elif mutation == "duplicate":
        raw = match_path.read_text()
        match_path.write_text(raw.replace('{"schema_version":1', '{"schema_version":1,"schema_version":1', 1))
    else:
        match_path.write_bytes(match_path.read_bytes() + b"{}")
    output = tmp_path / "result.json"
    output.write_text("stale", encoding="utf-8")
    proc = run(command(*paths, output))
    assert proc.returncode != 0
    assert not output.exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", 2),
        ("turn_count", 0),
        ("turn_count", 1001),
        ("turn_seconds", 0),
        ("turn_seconds", 86401),
    ],
)
def test_match_header_boundaries_are_validated(
    tmp_path: Path,
    field: str,
    value: int,
) -> None:
    match = make_match()
    match[field] = value
    assert_failure_without_output(tmp_path, match)


@pytest.mark.parametrize("case", ["duplicate-player", "bad-owner", "few-players"])
def test_player_and_owner_references_are_validated(tmp_path: Path, case: str) -> None:
    match = make_match()
    if case == "duplicate-player":
        match["players"].append(dict(match["players"][0]))
    elif case == "bad-owner":
        match["nodes"][0]["owner"] = "missing"
    else:
        match["players"] = [match["players"][0]]
    assert_failure_without_output(tmp_path, match)


@pytest.mark.parametrize("case", ["self", "duplicate", "reverse-duplicate", "unknown"])
def test_edge_invariants_are_validated(tmp_path: Path, case: str) -> None:
    match = make_match()
    if case == "self":
        match["edges"].append({"a": "A", "b": "A"})
    elif case == "duplicate":
        match["edges"].append({"a": "A", "b": "B"})
    elif case == "reverse-duplicate":
        match["edges"].append({"a": "B", "b": "A"})
    else:
        match["edges"].append({"a": "A", "b": "missing"})
    assert_failure_without_output(tmp_path, match)


@pytest.mark.parametrize("case", ["duplicate-id", "unknown-player", "unknown-node", "shared-node", "negative-draft"])
def test_fleet_invariants_are_validated(tmp_path: Path, case: str) -> None:
    match = make_match()
    if case == "duplicate-id":
        match["fleets"].append(dict(match["fleets"][0]))
    elif case == "unknown-player":
        match["fleets"][0]["player_id"] = "missing"
    elif case == "unknown-node":
        match["fleets"][0]["node_id"] = "missing"
    elif case == "shared-node":
        match["fleets"][1]["node_id"] = "A"
    else:
        match["fleets"][0]["draft_m"] = -0.1
    assert_failure_without_output(tmp_path, match)


@pytest.mark.parametrize(
    "order",
    [
        {"turn": 0, "fleet_id": "amber-1", "kind": "hold"},
        {"turn": 1, "fleet_id": "missing", "kind": "hold"},
        {"turn": 1, "fleet_id": "amber-1", "kind": "sail"},
        {"turn": 1, "fleet_id": "amber-1", "kind": "hold", "target_node_id": "B"},
        {"turn": 1, "fleet_id": "amber-1", "kind": "move"},
        {"turn": 1, "fleet_id": "amber-1", "kind": "move", "target_node_id": "missing"},
    ],
)
def test_order_shape_and_references_are_validated(
    tmp_path: Path,
    order: dict[str, object],
) -> None:
    assert_failure_without_output(tmp_path, make_match(orders=[order]))


def test_duplicate_order_for_same_fleet_and_turn_is_rejected(tmp_path: Path) -> None:
    order = {"turn": 1, "fleet_id": "amber-1", "kind": "hold"}
    assert_failure_without_output(tmp_path, make_match(orders=[order, dict(order)]))


def test_unknown_station_reference_is_rejected(tmp_path: Path) -> None:
    match = make_match()
    paths = write_case(tmp_path / "inputs", match)
    station_payload = json.loads(paths[1].read_text())
    station_payload["stations"] = [
        row for row in station_payload["stations"] if row["id"] != "station-A"
    ]
    paths[1].write_bytes(compact(station_payload) + b"\n")
    output = tmp_path / "result.json"
    output.write_text("stale", encoding="utf-8")
    proc = run(command(*paths, output))
    assert proc.returncode != 0
    assert not output.exists()


def test_relative_paths_and_nonpositive_threads_are_rejected(tmp_path: Path) -> None:
    paths = write_case(tmp_path / "inputs", make_match())
    output = tmp_path / "result.json"
    relative = run(
        [
            str(CLI),
            "adjudicate",
            "--match",
            "match.json",
            "--stations",
            str(paths[1]),
            "--catalog",
            str(paths[2]),
            "--leaps",
            str(paths[3]),
            "--threads",
            "1",
            "--output",
            str(output),
        ]
    )
    assert relative.returncode != 0
    nonpositive = run(command(*paths, output, threads=0))
    assert nonpositive.returncode != 0
    assert not output.exists()


def test_forecast_failure_removes_stale_game_output(tmp_path: Path) -> None:
    match = make_match(start_utc="2016-12-30T00:00:00Z")
    assert_failure_without_output(tmp_path, match)


def test_combined_contest_depth_capture_scoring_and_digest(tmp_path: Path) -> None:
    orders = [
        {"turn": 1, "fleet_id": "amber-1", "kind": "move", "target_node_id": "B"},
        {"turn": 1, "fleet_id": "cobalt-1", "kind": "move", "target_node_id": "B"},
        {"turn": 2, "fleet_id": "amber-1", "kind": "move", "target_node_id": "C"},
        {"turn": 2, "fleet_id": "cobalt-1", "kind": "move", "target_node_id": "D"},
    ]
    proc, _, payload = run_case(tmp_path, make_match(orders=orders, turn_count=2))
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-1", 1)["status"] == "moved"
    assert fleet_row(payload, "cobalt-1", 1)["status"] == "blocked-contest"
    assert fleet_row(payload, "amber-1", 2)["status"] == "moved"
    assert fleet_row(payload, "cobalt-1", 2)["status"] == "moved"
    assert payload["summary"]["sha256"] == expected_digest(payload)
