from __future__ import annotations

import copy
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
    station_bundle: dict[str, object] | None = None,
    catalog_entries: list[dict[str, object]] | None = None,
) -> tuple[Path, Path, Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    match_path = root / "match.json"
    stations_path = root / "stations.json"
    catalog_dir = root / "catalog"
    leaps_path = root / "leaps.txt"
    match_path.write_bytes(compact(match) + b"\n")
    catalog_dir.mkdir()
    if catalog_entries is None:
        shutil.copy2(APP / "examples/game/catalog/M2.json", catalog_dir / "M2.json")
    else:
        for entry in catalog_entries:
            name = str(entry["name"])
            (catalog_dir / f"{name}.json").write_bytes(compact(entry) + b"\n")
    shutil.copy2(APP / "examples/game/leaps.txt", leaps_path)
    if station_bundle is None:
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
        station_bundle = {"schema_version": 1, "stations": stations}
    stations_path.write_bytes(compact(station_bundle) + b"\n")
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
    station_bundle: dict[str, object] | None = None,
    catalog_entries: list[dict[str, object]] | None = None,
    threads: int = 2,
    cwd: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, dict[str, object] | None]:
    paths = write_case(
        tmp_path / "inputs",
        match,
        tides=tides,
        station_bundle=station_bundle,
        catalog_entries=catalog_entries,
    )
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


def test_nonzero_harmonics_sum_hermite_and_wrap_phase(tmp_path: Path) -> None:
    center_tai = 1483228837
    catalogs = [
        {
            "schema_version": 1,
            "name": "M2",
            "speed_deg_per_hour": 12.0,
            "epoch_tai": center_tai,
            "nodal": [
                {
                    "tai": center_tai - 10,
                    "factor": 0.8,
                    "factor_slope_per_sec": 0.01,
                    "phase_deg": 350.0,
                    "phase_slope_deg_per_sec": 1.5,
                },
                {
                    "tai": center_tai + 10,
                    "factor": 1.2,
                    "factor_slope_per_sec": -0.005,
                    "phase_deg": 10.0,
                    "phase_slope_deg_per_sec": -0.5,
                },
            ],
        },
        {
            "schema_version": 1,
            "name": "S2",
            "speed_deg_per_hour": 0.0,
            "epoch_tai": center_tai,
            "nodal": [
                {
                    "tai": center_tai - 10,
                    "factor": 1.1,
                    "factor_slope_per_sec": -0.002,
                    "phase_deg": 40.0,
                    "phase_slope_deg_per_sec": 0.2,
                },
                {
                    "tai": center_tai + 10,
                    "factor": 0.9,
                    "factor_slope_per_sec": 0.004,
                    "phase_deg": 80.0,
                    "phase_slope_deg_per_sec": -0.1,
                },
            ],
        },
    ]
    station_bundle = {
        "schema_version": 1,
        "global": {"datum_m": 0.1, "scale": 1.5, "phase_offset_deg": 5.0},
        "regions": {
            "north": {"datum_m": 0.2, "scale": 2.0, "phase_offset_deg": 15.0}
        },
        "stations": [
            {
                "id": "harmonic",
                "region": "north",
                "latitude_deg": 0.0,
                "longitude_deg": 20.0,
                "overrides": {
                    "datum_m": 0.3,
                    "scale": 1.25,
                    "phase_offset_deg": 25.0,
                },
                "constituents": [
                    {"name": "M2", "amplitude_m": 0.4, "phase_deg": 30.0, "required": True},
                    {"name": "S2", "amplitude_m": 0.2, "phase_deg": -50.0, "required": True},
                    {"name": "OPTIONAL", "amplitude_m": 9.0, "phase_deg": 120.0, "required": False},
                ],
            }
        ],
    }
    nodes = base_nodes()
    for node in nodes:
        node["station_id"] = "harmonic"
    proc, _, payload = run_case(
        tmp_path,
        make_match(start_utc="2017-01-01T00:00:00Z", nodes=nodes),
        station_bundle=station_bundle,
        catalog_entries=catalogs,
    )
    assert proc.returncode == 0, proc.stderr
    node = next(row for row in payload["turns"][0]["nodes"] if row["id"] == "A")
    assert node["tide_m"] == 0.528671
    assert node["effective_depth_m"] == 1.528671


def test_real_harmonic_variation_blocks_then_allows_move(tmp_path: Path) -> None:
    start_tai = 1483228837
    catalog = {
        "schema_version": 1,
        "name": "M2",
        "speed_deg_per_hour": 180.0,
        "epoch_tai": start_tai,
        "nodal": [
            {
                "tai": start_tai,
                "factor": 1.0,
                "factor_slope_per_sec": 0.0,
                "phase_deg": 0.0,
                "phase_slope_deg_per_sec": 0.0,
            },
            {
                "tai": start_tai + 7200,
                "factor": 1.0,
                "factor_slope_per_sec": 0.0,
                "phase_deg": 0.0,
                "phase_slope_deg_per_sec": 0.0,
            },
        ],
    }
    station_bundle = {
        "schema_version": 1,
        "stations": [
            {
                "id": "swing",
                "latitude_deg": 0.0,
                "longitude_deg": 0.0,
                "constituents": [
                    {"name": "M2", "amplitude_m": 0.2, "phase_deg": 180.0, "required": True}
                ],
            }
        ],
    }
    nodes = [
        {
            "id": "A",
            "station_id": "swing",
            "base_depth_m": 1.0,
            "value": 3,
            "owner": "amber",
        },
        {
            "id": "B",
            "station_id": "swing",
            "base_depth_m": 1.0,
            "value": 4,
        },
    ]
    fleets = [
        {"id": "amber-1", "player_id": "amber", "node_id": "A", "draft_m": 1.1}
    ]
    orders = [
        {"turn": 1, "fleet_id": "amber-1", "kind": "move", "target_node_id": "B"},
        {"turn": 2, "fleet_id": "amber-1", "kind": "move", "target_node_id": "B"},
    ]
    match = make_match(
        start_utc="2017-01-01T00:00:00Z",
        turn_seconds=3600,
        turn_count=2,
        nodes=nodes,
        edges=[{"a": "A", "b": "B"}],
        fleets=fleets,
        orders=orders,
    )
    proc, _, payload = run_case(
        tmp_path,
        match,
        station_bundle=station_bundle,
        catalog_entries=[catalog],
    )
    assert proc.returncode == 0, proc.stderr
    assert [turn["nodes"][0]["tide_m"] for turn in payload["turns"]] == [-0.2, 0.2]
    assert [turn["nodes"][0]["effective_depth_m"] for turn in payload["turns"]] == [0.8, 1.2]
    assert fleet_row(payload, "amber-1", 1)["status"] == "blocked-depth"
    assert fleet_row(payload, "amber-1", 2)["status"] == "moved"
    assert fleet_row(payload, "amber-1", 2)["node_id"] == "B"


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
    assert list(payload["turns"][0]) == ["turn", "utc", "nodes", "fleets", "score_delta", "scores"]


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


def owner_map(rows: list[dict[str, object]]) -> dict[str, str]:
    return {str(row["id"]): str(row.get("owner", "")) for row in rows}


def node_row(payload: dict[str, object], node_id: str, turn: int = 1) -> dict[str, object]:
    rows = payload["turns"][turn - 1]["nodes"]
    return next(row for row in rows if row["id"] == node_id)


def test_invalid_edge_precedes_depth_block(tmp_path: Path) -> None:
    """A nonadjacent move reports blocked-edge even when both endpoints are too shallow."""
    nodes = base_nodes()
    nodes[0]["base_depth_m"] = 0.2
    nodes[2]["base_depth_m"] = 0.2
    orders = [{"turn": 1, "fleet_id": "amber-1", "kind": "move", "target_node_id": "C"}]
    proc, _, payload = run_case(tmp_path, make_match(nodes=nodes, orders=orders))
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-1")["status"] == "blocked-edge"


def test_same_node_move_precedes_depth_block(tmp_path: Path) -> None:
    """A move to the fleet's current node is blocked-edge before depth is considered."""
    nodes = base_nodes()
    nodes[0]["base_depth_m"] = 0.2
    orders = [{"turn": 1, "fleet_id": "amber-1", "kind": "move", "target_node_id": "A"}]
    proc, _, payload = run_case(tmp_path, make_match(nodes=nodes, orders=orders))
    assert proc.returncode == 0, proc.stderr
    row = fleet_row(payload, "amber-1")
    assert row["status"] == "blocked-edge"
    assert row["node_id"] == "A"


def test_depth_blocked_high_initiative_fleet_does_not_enter_contest(tmp_path: Path) -> None:
    """Only depth-legal candidates participate in a same-target contest."""
    fleets = [
        {"id": "amber-1", "player_id": "amber", "node_id": "A", "draft_m": 1.1},
        {"id": "cobalt-1", "player_id": "cobalt", "node_id": "C", "draft_m": 0.5},
    ]
    orders = [
        {"turn": 1, "fleet_id": "amber-1", "kind": "move", "target_node_id": "B"},
        {"turn": 1, "fleet_id": "cobalt-1", "kind": "move", "target_node_id": "B"},
    ]
    proc, _, payload = run_case(tmp_path, make_match(fleets=fleets, orders=orders))
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-1")["status"] == "blocked-depth"
    assert fleet_row(payload, "cobalt-1")["status"] == "moved"


def test_edge_blocked_high_initiative_fleet_does_not_enter_contest(tmp_path: Path) -> None:
    """A nonadjacent high-priority order cannot defeat a legal lower-priority contender."""
    nodes = base_nodes()[:3]
    fleets = [
        {"id": "amber-1", "player_id": "amber", "node_id": "A", "draft_m": 0.5},
        {"id": "cobalt-1", "player_id": "cobalt", "node_id": "B", "draft_m": 0.5},
    ]
    orders = [
        {"turn": 1, "fleet_id": "amber-1", "kind": "move", "target_node_id": "C"},
        {"turn": 1, "fleet_id": "cobalt-1", "kind": "move", "target_node_id": "C"},
    ]
    proc, _, payload = run_case(
        tmp_path,
        make_match(nodes=nodes, edges=[{"a": "A", "b": "B"}, {"a": "B", "b": "C"}], fleets=fleets, orders=orders),
    )
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-1")["status"] == "blocked-edge"
    assert fleet_row(payload, "cobalt-1")["status"] == "moved"


def test_same_player_contest_uses_fleet_id(tmp_path: Path) -> None:
    """When player and initiative tie, the lexicographically smaller fleet ID wins."""
    players = [{"id": "alpha", "initiative": 2}, {"id": "beta", "initiative": 0}]
    nodes = base_nodes()[:3]
    nodes[0]["owner"] = "alpha"
    nodes[2]["owner"] = "beta"
    fleets = [
        {"id": "zeta", "player_id": "alpha", "node_id": "A", "draft_m": 0.5},
        {"id": "aardvark", "player_id": "alpha", "node_id": "C", "draft_m": 0.5},
    ]
    orders = [
        {"turn": 1, "fleet_id": "zeta", "kind": "move", "target_node_id": "B"},
        {"turn": 1, "fleet_id": "aardvark", "kind": "move", "target_node_id": "B"},
    ]
    proc, _, payload = run_case(
        tmp_path,
        make_match(players=players, nodes=nodes, edges=[{"a": "A", "b": "B"}, {"a": "C", "b": "B"}], fleets=fleets, orders=orders),
    )
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "aardvark")["status"] == "moved"
    assert fleet_row(payload, "zeta")["status"] == "blocked-contest"


def test_contest_winner_can_still_be_blocked_by_stationary_occupant(tmp_path: Path) -> None:
    """Winning target priority does not displace a stationary start-of-turn occupant."""
    players = base_players() + [{"id": "jade", "initiative": 0}]
    nodes = base_nodes()[:3]
    fleets = [
        {"id": "fa", "player_id": "amber", "node_id": "A", "draft_m": 0.5},
        {"id": "fb", "player_id": "jade", "node_id": "B", "draft_m": 0.5},
        {"id": "fc", "player_id": "cobalt", "node_id": "C", "draft_m": 0.5},
    ]
    orders = [
        {"turn": 1, "fleet_id": "fa", "kind": "move", "target_node_id": "B"},
        {"turn": 1, "fleet_id": "fc", "kind": "move", "target_node_id": "B"},
    ]
    proc, _, payload = run_case(
        tmp_path,
        make_match(players=players, nodes=nodes, edges=[{"a": "A", "b": "B"}, {"a": "C", "b": "B"}], fleets=fleets, orders=orders),
    )
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "fa")["status"] == "blocked-occupied"
    assert fleet_row(payload, "fc")["status"] == "blocked-contest"
    assert fleet_row(payload, "fb")["status"] == "hold"


def test_chain_contest_winner_vacates_and_unlocks_upstream(tmp_path: Path) -> None:
    """A contest winner that moves into an empty node can release an upstream chain."""
    players = [
        {"id": "amber", "initiative": 2},
        {"id": "cobalt", "initiative": 3},
        {"id": "jade", "initiative": 1},
    ]
    nodes = base_nodes()
    fleets = [
        {"id": "fa", "player_id": "amber", "node_id": "A", "draft_m": 0.5},
        {"id": "fb", "player_id": "cobalt", "node_id": "B", "draft_m": 0.5},
        {"id": "fd", "player_id": "jade", "node_id": "D", "draft_m": 0.5},
    ]
    orders = [
        {"turn": 1, "fleet_id": "fa", "kind": "move", "target_node_id": "B"},
        {"turn": 1, "fleet_id": "fb", "kind": "move", "target_node_id": "C"},
        {"turn": 1, "fleet_id": "fd", "kind": "move", "target_node_id": "C"},
    ]
    edges = [{"a": "A", "b": "B"}, {"a": "B", "b": "C"}, {"a": "D", "b": "C"}]
    proc, _, payload = run_case(tmp_path, make_match(players=players, nodes=nodes, edges=edges, fleets=fleets, orders=orders))
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "fa")["status"] == "moved"
    assert fleet_row(payload, "fb")["status"] == "moved"
    assert fleet_row(payload, "fd")["status"] == "blocked-contest"


def test_chain_contest_loser_stays_and_blocks_upstream(tmp_path: Path) -> None:
    """A contest loser remains at its source and blocks a selected upstream move."""
    players = [
        {"id": "amber", "initiative": 2},
        {"id": "cobalt", "initiative": 1},
        {"id": "jade", "initiative": 3},
    ]
    nodes = base_nodes()
    fleets = [
        {"id": "fa", "player_id": "amber", "node_id": "A", "draft_m": 0.5},
        {"id": "fb", "player_id": "cobalt", "node_id": "B", "draft_m": 0.5},
        {"id": "fd", "player_id": "jade", "node_id": "D", "draft_m": 0.5},
    ]
    orders = [
        {"turn": 1, "fleet_id": "fa", "kind": "move", "target_node_id": "B"},
        {"turn": 1, "fleet_id": "fb", "kind": "move", "target_node_id": "C"},
        {"turn": 1, "fleet_id": "fd", "kind": "move", "target_node_id": "C"},
    ]
    edges = [{"a": "A", "b": "B"}, {"a": "B", "b": "C"}, {"a": "D", "b": "C"}]
    proc, _, payload = run_case(tmp_path, make_match(players=players, nodes=nodes, edges=edges, fleets=fleets, orders=orders))
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "fa")["status"] == "blocked-occupied"
    assert fleet_row(payload, "fb")["status"] == "blocked-contest"
    assert fleet_row(payload, "fd")["status"] == "moved"


def test_four_fleet_chain_into_empty_node_succeeds(tmp_path: Path) -> None:
    """Every selected move in a long dependency chain succeeds when the tail is empty."""
    nodes = [
        {"id": name, "station_id": f"station-{name}", "base_depth_m": 2.0, "value": index + 1}
        for index, name in enumerate("ABCDE")
    ]
    edges = [{"a": left, "b": right} for left, right in zip("ABCD", "BCDE")]
    fleets = [
        {"id": f"f-{name}", "player_id": "amber" if index % 2 == 0 else "cobalt", "node_id": name, "draft_m": 1.0}
        for index, name in enumerate("ABCD")
    ]
    orders = [
        {"turn": 1, "fleet_id": f"f-{left}", "kind": "move", "target_node_id": right}
        for left, right in zip("ABCD", "BCDE")
    ]
    proc, _, payload = run_case(tmp_path, make_match(nodes=nodes, edges=edges, fleets=fleets, orders=orders))
    assert proc.returncode == 0, proc.stderr
    assert [fleet_row(payload, f"f-{name}")["status"] for name in "ABCD"] == ["moved"] * 4
    assert [fleet_row(payload, f"f-{name}")["node_id"] for name in "ABCD"] == list("BCDE")


def test_four_fleet_chain_to_stationary_fleet_fails(tmp_path: Path) -> None:
    """A long selected chain fails throughout when its final occupant does not move."""
    nodes = [
        {"id": name, "station_id": f"station-{name}", "base_depth_m": 2.0, "value": index + 1}
        for index, name in enumerate("ABCDE")
    ]
    edges = [{"a": left, "b": right} for left, right in zip("ABCD", "BCDE")]
    fleets = [
        {"id": f"f-{name}", "player_id": "amber" if index % 2 == 0 else "cobalt", "node_id": name, "draft_m": 1.0}
        for index, name in enumerate("ABCDE")
    ]
    orders = [
        {"turn": 1, "fleet_id": f"f-{left}", "kind": "move", "target_node_id": right}
        for left, right in zip("ABCD", "BCDE")
    ]
    proc, _, payload = run_case(tmp_path, make_match(nodes=nodes, edges=edges, fleets=fleets, orders=orders))
    assert proc.returncode == 0, proc.stderr
    assert [fleet_row(payload, f"f-{name}")["status"] for name in "ABCD"] == ["blocked-occupied"] * 4
    assert fleet_row(payload, "f-E")["status"] == "hold"


def test_cycle_broken_by_depth_failure_blocks_other_legs(tmp_path: Path) -> None:
    """A depth-invalid leg stays put and prevents the remaining selected cycle legs."""
    players = base_players() + [{"id": "jade", "initiative": 0}]
    nodes = base_nodes()[:3]
    fleets = [
        {"id": "fa", "player_id": "amber", "node_id": "A", "draft_m": 0.5},
        {"id": "fb", "player_id": "cobalt", "node_id": "B", "draft_m": 0.5},
        {"id": "fc", "player_id": "jade", "node_id": "C", "draft_m": 1.1},
    ]
    orders = [
        {"turn": 1, "fleet_id": "fa", "kind": "move", "target_node_id": "B"},
        {"turn": 1, "fleet_id": "fb", "kind": "move", "target_node_id": "C"},
        {"turn": 1, "fleet_id": "fc", "kind": "move", "target_node_id": "A"},
    ]
    edges = [{"a": "A", "b": "B"}, {"a": "B", "b": "C"}, {"a": "C", "b": "A"}]
    proc, _, payload = run_case(tmp_path, make_match(players=players, nodes=nodes, edges=edges, fleets=fleets, orders=orders))
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "fc")["status"] == "blocked-depth"
    assert fleet_row(payload, "fb")["status"] == "blocked-occupied"
    assert fleet_row(payload, "fa")["status"] == "blocked-occupied"


def test_cycle_broken_by_edge_failure_blocks_other_legs(tmp_path: Path) -> None:
    """A nonadjacent leg stays put and prevents the remaining selected cycle legs."""
    players = base_players() + [{"id": "jade", "initiative": 0}]
    nodes = base_nodes()[:3]
    fleets = [
        {"id": "fa", "player_id": "amber", "node_id": "A", "draft_m": 0.5},
        {"id": "fb", "player_id": "cobalt", "node_id": "B", "draft_m": 0.5},
        {"id": "fc", "player_id": "jade", "node_id": "C", "draft_m": 0.5},
    ]
    orders = [
        {"turn": 1, "fleet_id": "fa", "kind": "move", "target_node_id": "B"},
        {"turn": 1, "fleet_id": "fb", "kind": "move", "target_node_id": "C"},
        {"turn": 1, "fleet_id": "fc", "kind": "move", "target_node_id": "A"},
    ]
    edges = [{"a": "A", "b": "B"}, {"a": "B", "b": "C"}]
    proc, _, payload = run_case(tmp_path, make_match(players=players, nodes=nodes, edges=edges, fleets=fleets, orders=orders))
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "fc")["status"] == "blocked-edge"
    assert fleet_row(payload, "fb")["status"] == "blocked-occupied"
    assert fleet_row(payload, "fa")["status"] == "blocked-occupied"


def test_disjoint_cycle_chain_and_hold_resolve_together(tmp_path: Path) -> None:
    """Independent swaps, chains, captures, and holds resolve in one simultaneous turn."""
    nodes = [
        {"id": name, "station_id": f"station-{name}", "base_depth_m": 2.0, "value": index + 1}
        for index, name in enumerate("ABCDEF")
    ]
    edges = [{"a": "A", "b": "B"}, {"a": "C", "b": "D"}, {"a": "D", "b": "E"}]
    fleets = [
        {"id": "fa", "player_id": "amber", "node_id": "A", "draft_m": 1.0},
        {"id": "fb", "player_id": "cobalt", "node_id": "B", "draft_m": 1.0},
        {"id": "fc", "player_id": "amber", "node_id": "C", "draft_m": 1.0},
        {"id": "fd", "player_id": "cobalt", "node_id": "D", "draft_m": 1.0},
        {"id": "ff", "player_id": "amber", "node_id": "F", "draft_m": 1.0},
    ]
    orders = [
        {"turn": 1, "fleet_id": "fa", "kind": "move", "target_node_id": "B"},
        {"turn": 1, "fleet_id": "fb", "kind": "move", "target_node_id": "A"},
        {"turn": 1, "fleet_id": "fc", "kind": "move", "target_node_id": "D"},
        {"turn": 1, "fleet_id": "fd", "kind": "move", "target_node_id": "E"},
    ]
    proc, _, payload = run_case(tmp_path, make_match(nodes=nodes, edges=edges, fleets=fleets, orders=orders))
    assert proc.returncode == 0, proc.stderr
    assert {fleet_row(payload, fleet)["status"] for fleet in ["fa", "fb", "fc", "fd"]} == {"moved"}
    assert fleet_row(payload, "ff")["status"] == "hold"
    assert owner_map(payload["turns"][0]["nodes"])["E"] == "cobalt"
    assert payload["summary"]["sha256"] == expected_digest(payload)


def test_orders_apply_from_current_positions_across_turns(tmp_path: Path) -> None:
    """A later order uses the node reached on the preceding turn as its source."""
    nodes = base_nodes()[:3]
    fleets = [{"id": "fa", "player_id": "amber", "node_id": "A", "draft_m": 0.5}]
    orders = [
        {"turn": 1, "fleet_id": "fa", "kind": "move", "target_node_id": "B"},
        {"turn": 2, "fleet_id": "fa", "kind": "move", "target_node_id": "C"},
    ]
    proc, _, payload = run_case(
        tmp_path,
        make_match(nodes=nodes, edges=[{"a": "A", "b": "B"}, {"a": "B", "b": "C"}], fleets=fleets, orders=orders, turn_count=2),
    )
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "fa", 1)["node_id"] == "B"
    assert fleet_row(payload, "fa", 2)["node_id"] == "C"
    assert fleet_row(payload, "fa", 2)["status"] == "moved"


def test_missing_later_order_holds_at_new_position(tmp_path: Path) -> None:
    """An omitted later order becomes a hold at the fleet's updated position."""
    nodes = base_nodes()[:2]
    fleets = [{"id": "fa", "player_id": "amber", "node_id": "A", "draft_m": 0.5}]
    orders = [{"turn": 1, "fleet_id": "fa", "kind": "move", "target_node_id": "B"}]
    proc, _, payload = run_case(
        tmp_path,
        make_match(nodes=nodes, edges=[{"a": "A", "b": "B"}], fleets=fleets, orders=orders, turn_count=2),
    )
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "fa", 2) == {
        "id": "fa",
        "player_id": "amber",
        "node_id": "B",
        "order": "hold",
        "status": "hold",
    }


def test_vacated_owned_node_retains_owner(tmp_path: Path) -> None:
    """A successful departure does not neutralize territory that was already owned."""
    nodes = base_nodes()[:2]
    nodes[0]["owner"] = "amber"
    fleets = [{"id": "fa", "player_id": "amber", "node_id": "A", "draft_m": 0.5}]
    orders = [{"turn": 1, "fleet_id": "fa", "kind": "move", "target_node_id": "B"}]
    proc, _, payload = run_case(tmp_path, make_match(nodes=nodes, edges=[{"a": "A", "b": "B"}], fleets=fleets, orders=orders))
    assert proc.returncode == 0, proc.stderr
    assert owner_map(payload["turns"][0]["nodes"]) == {"A": "amber", "B": "amber"}


def test_vacated_unowned_node_remains_unowned(tmp_path: Path) -> None:
    """Leaving an initially neutral source does not retroactively capture it."""
    nodes = base_nodes()[:2]
    nodes[0].pop("owner", None)
    fleets = [{"id": "fa", "player_id": "amber", "node_id": "A", "draft_m": 0.5}]
    orders = [{"turn": 1, "fleet_id": "fa", "kind": "move", "target_node_id": "B"}]
    proc, _, payload = run_case(tmp_path, make_match(nodes=nodes, edges=[{"a": "A", "b": "B"}], fleets=fleets, orders=orders))
    assert proc.returncode == 0, proc.stderr
    owners = owner_map(payload["turns"][0]["nodes"])
    assert owners["A"] == ""
    assert owners["B"] == "amber"


def test_cycle_capture_assigns_arriving_players_and_scores(tmp_path: Path) -> None:
    """A cycle captures each destination for its arriving player before scoring all territory."""
    players = base_players() + [{"id": "jade", "initiative": 0}]
    nodes = base_nodes()[:3]
    nodes[0].update({"owner": "amber", "value": 2})
    nodes[1].update({"owner": "cobalt", "value": 3})
    nodes[2].update({"owner": "jade", "value": 5})
    fleets = [
        {"id": "fa", "player_id": "amber", "node_id": "A", "draft_m": 0.5},
        {"id": "fb", "player_id": "cobalt", "node_id": "B", "draft_m": 0.5},
        {"id": "fc", "player_id": "jade", "node_id": "C", "draft_m": 0.5},
    ]
    orders = [
        {"turn": 1, "fleet_id": "fa", "kind": "move", "target_node_id": "B"},
        {"turn": 1, "fleet_id": "fb", "kind": "move", "target_node_id": "C"},
        {"turn": 1, "fleet_id": "fc", "kind": "move", "target_node_id": "A"},
    ]
    edges = [{"a": "A", "b": "B"}, {"a": "B", "b": "C"}, {"a": "C", "b": "A"}]
    proc, _, payload = run_case(tmp_path, make_match(players=players, nodes=nodes, edges=edges, fleets=fleets, orders=orders))
    assert proc.returncode == 0, proc.stderr
    assert owner_map(payload["turns"][0]["nodes"]) == {"A": "jade", "B": "amber", "C": "cobalt"}
    assert score_map(payload["turns"][0]["score_delta"]) == {"amber": 3, "cobalt": 5, "jade": 2}


def test_blocked_move_captures_source_but_not_target(tmp_path: Path) -> None:
    """A blocked fleet still captures its occupied source while leaving its target unchanged."""
    nodes = base_nodes()[:3]
    nodes[0]["owner"] = "cobalt"
    nodes[2]["owner"] = "cobalt"
    fleets = [{"id": "fa", "player_id": "amber", "node_id": "A", "draft_m": 0.5}]
    orders = [{"turn": 1, "fleet_id": "fa", "kind": "move", "target_node_id": "C"}]
    proc, _, payload = run_case(
        tmp_path,
        make_match(nodes=nodes, edges=[{"a": "A", "b": "B"}, {"a": "B", "b": "C"}], fleets=fleets, orders=orders),
    )
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "fa")["status"] == "blocked-edge"
    owners = owner_map(payload["turns"][0]["nodes"])
    assert owners["A"] == "amber"
    assert owners["C"] == "cobalt"


def test_score_delta_repeats_retained_territory_each_turn(tmp_path: Path) -> None:
    """Each turn scores every currently owned node rather than only newly captured nodes."""
    nodes = base_nodes()[:2]
    nodes[0].update({"owner": "amber", "value": 7})
    nodes[1].update({"owner": "cobalt", "value": 4})
    fleets = [{"id": "fa", "player_id": "amber", "node_id": "A", "draft_m": 0.5}]
    proc, _, payload = run_case(tmp_path, make_match(nodes=nodes, edges=[], fleets=fleets, turn_count=3))
    assert proc.returncode == 0, proc.stderr
    deltas = [score_map(turn["score_delta"]) for turn in payload["turns"]]
    assert deltas == [{"amber": 7, "cobalt": 4}] * 3
    assert score_map(payload["turns"][2]["scores"]) == {"amber": 21, "cobalt": 12}


def test_player_without_fleet_can_win_on_owned_territory(tmp_path: Path) -> None:
    """Winner selection includes players who retain territory without controlling a fleet."""
    players = [{"id": "alpha", "initiative": 2}, {"id": "zulu", "initiative": 0}]
    nodes = [
        {"id": "A", "station_id": "station-A", "base_depth_m": 1.0, "value": 2},
        {"id": "B", "station_id": "station-B", "base_depth_m": 1.0, "value": 9, "owner": "zulu"},
    ]
    fleets = [{"id": "fa", "player_id": "alpha", "node_id": "A", "draft_m": 0.5}]
    proc, _, payload = run_case(tmp_path, make_match(players=players, nodes=nodes, edges=[], fleets=fleets))
    assert proc.returncode == 0, proc.stderr
    assert score_map(payload["final"]["scores"]) == {"alpha": 2, "zulu": 9}
    assert payload["final"]["winner"] == "zulu"


def test_final_player_id_breaks_equal_score_and_initiative(tmp_path: Path) -> None:
    """Equal final scores and initiatives are resolved by lexicographically smaller player ID."""
    players = [{"id": "zulu", "initiative": 1}, {"id": "alpha", "initiative": 1}]
    nodes = [
        {"id": "A", "station_id": "station-A", "base_depth_m": 1.0, "value": 3, "owner": "zulu"},
        {"id": "B", "station_id": "station-B", "base_depth_m": 1.0, "value": 3, "owner": "alpha"},
    ]
    fleets = [
        {"id": "fz", "player_id": "zulu", "node_id": "A", "draft_m": 0.5},
        {"id": "fa", "player_id": "alpha", "node_id": "B", "draft_m": 0.5},
    ]
    proc, _, payload = run_case(tmp_path, make_match(players=players, nodes=nodes, edges=[], fleets=fleets))
    assert proc.returncode == 0, proc.stderr
    assert score_map(payload["final"]["scores"]) == {"alpha": 3, "zulu": 3}
    assert payload["final"]["winner"] == "alpha"


def test_rounding_before_depth_check_can_admit_move(tmp_path: Path) -> None:
    """Draft legality uses six-decimal effective depth, allowing a raw value that rounds up."""
    nodes = base_nodes()[:2]
    for node in nodes:
        node["base_depth_m"] = 0.9999996
    fleets = [{"id": "fa", "player_id": "amber", "node_id": "A", "draft_m": 1.0}]
    orders = [{"turn": 1, "fleet_id": "fa", "kind": "move", "target_node_id": "B"}]
    proc, _, payload = run_case(tmp_path, make_match(nodes=nodes, edges=[{"a": "A", "b": "B"}], fleets=fleets, orders=orders))
    assert proc.returncode == 0, proc.stderr
    assert node_row(payload, "A")["effective_depth_m"] == 1.0
    assert node_row(payload, "B")["effective_depth_m"] == 1.0
    assert fleet_row(payload, "fa")["status"] == "moved"


def test_rounding_before_depth_check_can_block_move(tmp_path: Path) -> None:
    """Draft legality uses six-decimal effective depth, blocking a raw value that rounds down."""
    nodes = base_nodes()[:2]
    for node in nodes:
        node["base_depth_m"] = 0.9999994
    fleets = [{"id": "fa", "player_id": "amber", "node_id": "A", "draft_m": 1.0}]
    orders = [{"turn": 1, "fleet_id": "fa", "kind": "move", "target_node_id": "B"}]
    proc, _, payload = run_case(tmp_path, make_match(nodes=nodes, edges=[{"a": "A", "b": "B"}], fleets=fleets, orders=orders))
    assert proc.returncode == 0, proc.stderr
    assert node_row(payload, "A")["effective_depth_m"] == 0.999999
    assert fleet_row(payload, "fa")["status"] == "blocked-depth"


def test_negative_half_even_rounding_and_negative_zero_normalization(tmp_path: Path) -> None:
    """Negative ties round to even and values rounding to zero serialize without a minus sign."""
    proc, output, payload = run_case(
        tmp_path,
        make_match(),
        tides={"station-A": -0.1234565, "station-B": -0.0000004},
    )
    assert proc.returncode == 0, proc.stderr
    assert node_row(payload, "A")["tide_m"] == -0.123456
    assert node_row(payload, "A")["effective_depth_m"] == 0.876544
    assert node_row(payload, "B")["tide_m"] == 0
    assert b'"id":"B","tide_m":-0' not in output.read_bytes()


def test_tai_step_of_two_crosses_declared_leap_second_correctly(tmp_path: Path) -> None:
    """TAI stepping by two seconds crosses the declared leap without treating UTC as uniform."""
    proc, _, payload = run_case(tmp_path, make_match(turn_seconds=2, turn_count=3))
    assert proc.returncode == 0, proc.stderr
    assert [turn["utc"] for turn in payload["turns"]] == [
        "2016-12-31T23:59:59Z",
        "2017-01-01T00:00:00Z",
        "2017-01-01T00:00:02Z",
    ]


def test_digest_changes_when_status_changes_without_position_change(tmp_path: Path) -> None:
    """The summary digest records fleet status even when final positions are identical."""
    hold_match = make_match(
        match_id="digest-status",
        orders=[{"turn": 1, "fleet_id": "amber-1", "kind": "hold"}],
    )
    blocked_match = make_match(
        match_id="digest-status",
        orders=[{"turn": 1, "fleet_id": "amber-1", "kind": "move", "target_node_id": "C"}],
    )
    proc_a, _, payload_a = run_case(tmp_path / "hold", hold_match)
    proc_b, _, payload_b = run_case(tmp_path / "blocked", blocked_match)
    assert proc_a.returncode == 0, proc_a.stderr
    assert proc_b.returncode == 0, proc_b.stderr
    assert fleet_row(payload_a, "amber-1")["node_id"] == fleet_row(payload_b, "amber-1")["node_id"] == "A"
    assert payload_a["final"] == payload_b["final"]
    assert payload_a["summary"]["sha256"] != payload_b["summary"]["sha256"]
    assert payload_a["summary"]["sha256"] == expected_digest(payload_a)
    assert payload_b["summary"]["sha256"] == expected_digest(payload_b)


def test_complex_result_is_invariant_to_all_input_orderings(tmp_path: Path) -> None:
    """A contest feeding a dependency chain produces identical bytes under array reordering."""
    players = [
        {"id": "amber", "initiative": 2},
        {"id": "cobalt", "initiative": 3},
        {"id": "jade", "initiative": 1},
    ]
    nodes = base_nodes()
    fleets = [
        {"id": "fa", "player_id": "amber", "node_id": "A", "draft_m": 0.5},
        {"id": "fb", "player_id": "cobalt", "node_id": "B", "draft_m": 0.5},
        {"id": "fd", "player_id": "jade", "node_id": "D", "draft_m": 0.5},
    ]
    orders = [
        {"turn": 1, "fleet_id": "fa", "kind": "move", "target_node_id": "B"},
        {"turn": 1, "fleet_id": "fb", "kind": "move", "target_node_id": "C"},
        {"turn": 1, "fleet_id": "fd", "kind": "move", "target_node_id": "C"},
    ]
    edges = [{"a": "A", "b": "B"}, {"a": "B", "b": "C"}, {"a": "D", "b": "C"}]
    first = make_match(match_id="ordered-complex", players=players, nodes=nodes, edges=edges, fleets=fleets, orders=orders)
    second = make_match(
        match_id="ordered-complex",
        players=list(reversed(players)),
        nodes=list(reversed(nodes)),
        edges=list(reversed([{"a": edge["b"], "b": edge["a"]} for edge in edges])),
        fleets=list(reversed(fleets)),
        orders=list(reversed(orders)),
    )
    proc_a, out_a, payload_a = run_case(tmp_path / "first", first, threads=1)
    proc_b, out_b, payload_b = run_case(tmp_path / "second", second, threads=7)
    assert proc_a.returncode == 0, proc_a.stderr
    assert proc_b.returncode == 0, proc_b.stderr
    assert out_a.read_bytes() == out_b.read_bytes()
    assert payload_a["summary"]["sha256"] == expected_digest(payload_a)
    assert payload_b["summary"]["sha256"] == expected_digest(payload_b)


def test_nonzero_harmonic_result_is_invariant_across_threads(tmp_path: Path) -> None:
    """Concurrent nonzero harmonic forecasts remain byte-identical across worker counts and station order."""
    start_tai = 1483228837
    catalog = {
        "schema_version": 1,
        "name": "M2",
        "speed_deg_per_hour": 15.0,
        "epoch_tai": start_tai,
        "nodal": [
            {"tai": start_tai - 100, "factor": 0.9, "factor_slope_per_sec": 0.001, "phase_deg": 350.0, "phase_slope_deg_per_sec": 0.2},
            {"tai": start_tai + 100, "factor": 1.1, "factor_slope_per_sec": -0.001, "phase_deg": 10.0, "phase_slope_deg_per_sec": -0.1},
        ],
    }
    stations = [
        {
            "id": f"station-{index}",
            "latitude_deg": float(index),
            "longitude_deg": float(index * 17 - 40),
            "overrides": {"datum_m": index / 100.0, "scale": 1.0 + index / 20.0},
            "constituents": [{"name": "M2", "amplitude_m": 0.1 + index / 50.0, "phase_deg": index * 13.0, "required": True}],
        }
        for index in range(6)
    ]
    nodes = [
        {"id": f"N{index}", "station_id": f"station-{index}", "base_depth_m": 2.0, "value": index + 1}
        for index in range(6)
    ]
    fleets = [{"id": "fa", "player_id": "amber", "node_id": "N0", "draft_m": 0.5}]
    match = make_match(
        match_id="threaded-harmonics",
        start_utc="2017-01-01T00:00:00Z",
        turn_seconds=20,
        turn_count=3,
        nodes=nodes,
        edges=[],
        fleets=fleets,
    )
    bundle_a = {"schema_version": 1, "stations": stations}
    bundle_b = {"schema_version": 1, "stations": list(reversed(stations))}
    proc_a, out_a, payload_a = run_case(
        tmp_path / "one",
        match,
        station_bundle=bundle_a,
        catalog_entries=[catalog],
        threads=1,
    )
    proc_b, out_b, payload_b = run_case(
        tmp_path / "many",
        match,
        station_bundle=bundle_b,
        catalog_entries=[catalog],
        threads=12,
    )
    assert proc_a.returncode == 0, proc_a.stderr
    assert proc_b.returncode == 0, proc_b.stderr
    assert out_a.read_bytes() == out_b.read_bytes()
    assert any(node["tide_m"] != 0 for node in payload_a["turns"][0]["nodes"])
    assert payload_a["summary"]["sha256"] == expected_digest(payload_a)
    assert payload_b["summary"]["sha256"] == expected_digest(payload_b)


def test_two_independent_contests_resolve_without_cross_talk(tmp_path: Path) -> None:
    """Two simultaneous target contests select their own winners and capture independently."""
    players = [
        {"id": "amber", "initiative": 3},
        {"id": "cobalt", "initiative": 2},
        {"id": "jade", "initiative": 1},
    ]
    nodes = [
        {"id": name, "station_id": f"station-{name}", "base_depth_m": 2.0, "value": index + 1}
        for index, name in enumerate("ABCDEF")
    ]
    fleets = [
        {"id": "fa", "player_id": "amber", "node_id": "A", "draft_m": 1.0},
        {"id": "fc", "player_id": "cobalt", "node_id": "C", "draft_m": 1.0},
        {"id": "fd", "player_id": "jade", "node_id": "D", "draft_m": 1.0},
        {"id": "ff", "player_id": "cobalt", "node_id": "F", "draft_m": 1.0},
    ]
    orders = [
        {"turn": 1, "fleet_id": "fa", "kind": "move", "target_node_id": "B"},
        {"turn": 1, "fleet_id": "fc", "kind": "move", "target_node_id": "B"},
        {"turn": 1, "fleet_id": "fd", "kind": "move", "target_node_id": "E"},
        {"turn": 1, "fleet_id": "ff", "kind": "move", "target_node_id": "E"},
    ]
    edges = [
        {"a": "A", "b": "B"},
        {"a": "C", "b": "B"},
        {"a": "D", "b": "E"},
        {"a": "F", "b": "E"},
    ]
    proc, _, payload = run_case(tmp_path, make_match(players=players, nodes=nodes, edges=edges, fleets=fleets, orders=orders))
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "fa")["status"] == "moved"
    assert fleet_row(payload, "fc")["status"] == "blocked-contest"
    assert fleet_row(payload, "fd")["status"] == "blocked-contest"
    assert fleet_row(payload, "ff")["status"] == "moved"
    owners = owner_map(payload["turns"][0]["nodes"])
    assert owners["B"] == "amber"
    assert owners["E"] == "cobalt"
    assert payload["summary"]["sha256"] == expected_digest(payload)



def support_nodes(*ids: str, depth: float = 1.0) -> list[dict[str, object]]:
    return [
        {
            "id": node_id,
            "station_id": f"station-{node_id}",
            "base_depth_m": depth,
            "value": index + 1,
        }
        for index, node_id in enumerate(ids)
    ]


def complete_edges(*ids: str) -> list[dict[str, str]]:
    return [
        {"a": ids[left], "b": ids[right]}
        for left in range(len(ids))
        for right in range(left + 1, len(ids))
    ]


def fleet(
    fleet_id: str,
    player_id: str,
    node_id: str,
    *,
    draft: float = 1.0,
) -> dict[str, object]:
    return {
        "id": fleet_id,
        "player_id": player_id,
        "node_id": node_id,
        "draft_m": draft,
    }


def move(turn: int, fleet_id: str, target: str) -> dict[str, object]:
    return {
        "turn": turn,
        "fleet_id": fleet_id,
        "kind": "move",
        "target_node_id": target,
    }


def support(
    turn: int,
    fleet_id: str,
    supported_fleet_id: str,
    target: str,
) -> dict[str, object]:
    return {
        "turn": turn,
        "fleet_id": fleet_id,
        "kind": "support",
        "supported_fleet_id": supported_fleet_id,
        "target_node_id": target,
    }


def support_players(
    *, amber_initiative: int = 1, cobalt_initiative: int = 9
) -> list[dict[str, object]]:
    return [
        {"id": "amber", "initiative": amber_initiative},
        {"id": "cobalt", "initiative": cobalt_initiative},
    ]


def test_support_order_requires_supported_fleet_id(tmp_path: Path) -> None:
    """A support order without the named allied fleet is a fatal shape error."""
    order = {"turn": 1, "fleet_id": "amber-1", "kind": "support", "target_node_id": "B"}
    assert_failure_without_output(tmp_path, make_match(orders=[order]))


def test_support_order_requires_target_node_id(tmp_path: Path) -> None:
    """A support order without its supported destination is rejected fail-closed."""
    order = {
        "turn": 1,
        "fleet_id": "amber-1",
        "kind": "support",
        "supported_fleet_id": "cobalt-1",
    }
    assert_failure_without_output(tmp_path, make_match(orders=[order]))


def test_support_order_rejects_unknown_supported_fleet(tmp_path: Path) -> None:
    """Support must reference a fleet present in the validated match."""
    assert_failure_without_output(
        tmp_path,
        make_match(orders=[support(1, "amber-1", "missing", "B")]),
    )


def test_support_order_rejects_self_support(tmp_path: Path) -> None:
    """A fleet cannot add strength to its own move through a support order."""
    assert_failure_without_output(
        tmp_path,
        make_match(orders=[support(1, "amber-1", "amber-1", "B")]),
    )


def test_support_order_rejects_cross_player_support(tmp_path: Path) -> None:
    """Support is allied-only and cross-player support is invalid input."""
    assert_failure_without_output(
        tmp_path,
        make_match(orders=[support(1, "amber-1", "cobalt-1", "B")]),
    )


def test_support_order_rejects_unknown_target(tmp_path: Path) -> None:
    """The destination named by support must be an existing board node."""
    fleets = base_fleets() + [fleet("amber-2", "amber", "D")]
    assert_failure_without_output(
        tmp_path,
        make_match(
            fleets=fleets,
            orders=[support(1, "amber-2", "amber-1", "missing")],
        ),
    )


def test_hold_order_rejects_support_fields(tmp_path: Path) -> None:
    """Hold orders cannot smuggle target or supported-fleet fields."""
    order = {
        "turn": 1,
        "fleet_id": "amber-1",
        "kind": "hold",
        "supported_fleet_id": "cobalt-1",
    }
    assert_failure_without_output(tmp_path, make_match(orders=[order]))


def test_move_order_rejects_supported_fleet_id(tmp_path: Path) -> None:
    """Move rows accept only a target and reject support-only fields."""
    order = move(1, "amber-1", "B")
    order["supported_fleet_id"] = "cobalt-1"
    assert_failure_without_output(tmp_path, make_match(orders=[order]))


def test_move_fleet_row_has_exact_documented_shape(tmp_path: Path) -> None:
    """A successful move row has every required field and no support-only field."""
    proc, _, payload = run_case(
        tmp_path,
        make_match(orders=[move(1, "amber-1", "B")]),
    )
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-1") == {
        "id": "amber-1",
        "player_id": "amber",
        "node_id": "B",
        "order": "move",
        "target_node_id": "B",
        "status": "moved",
    }


def test_valid_support_row_is_complete_and_supporter_holds(tmp_path: Path) -> None:
    """Active support is reported canonically while the supporter stays in place."""
    nodes = support_nodes("A", "B", "E", "F")
    fleets = [
        fleet("amber-m", "amber", "A"),
        fleet("amber-s", "amber", "B"),
        fleet("cobalt-h", "cobalt", "F"),
    ]
    match = make_match(
        players=support_players(),
        nodes=nodes,
        edges=complete_edges("A", "B", "E", "F"),
        fleets=fleets,
        orders=[move(1, "amber-m", "E"), support(1, "amber-s", "amber-m", "E")],
    )
    proc, _, payload = run_case(tmp_path, match)
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-s") == {
        "id": "amber-s",
        "player_id": "amber",
        "node_id": "B",
        "order": "support",
        "target_node_id": "E",
        "supported_fleet_id": "amber-m",
        "status": "supported",
    }


def test_support_target_must_be_adjacent_from_current_position(tmp_path: Path) -> None:
    """A supporter that cannot reach the named target contributes no strength."""
    nodes = support_nodes("A", "B", "E", "F")
    fleets = [
        fleet("amber-m", "amber", "A"),
        fleet("amber-s", "amber", "B"),
        fleet("cobalt-h", "cobalt", "F"),
    ]
    match = make_match(
        players=support_players(),
        nodes=nodes,
        edges=[{"a": "A", "b": "E"}, {"a": "B", "b": "F"}],
        fleets=fleets,
        orders=[move(1, "amber-m", "E"), support(1, "amber-s", "amber-m", "E")],
    )
    proc, _, payload = run_case(tmp_path, match)
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-s")["status"] == "support-invalid"
    assert fleet_row(payload, "amber-m")["status"] == "moved"


def test_support_target_cannot_be_supporters_current_node(tmp_path: Path) -> None:
    """A fleet cannot support an allied move into the node it continues to occupy."""
    nodes = support_nodes("A", "B", "F")
    fleets = [
        fleet("amber-m", "amber", "A"),
        fleet("amber-s", "amber", "B"),
        fleet("cobalt-h", "cobalt", "F"),
    ]
    match = make_match(
        players=support_players(),
        nodes=nodes,
        edges=complete_edges("A", "B", "F"),
        fleets=fleets,
        orders=[move(1, "amber-m", "B"), support(1, "amber-s", "amber-m", "B")],
    )
    proc, _, payload = run_case(tmp_path, match)
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-s")["status"] == "support-invalid"
    assert fleet_row(payload, "amber-m")["status"] == "blocked-occupied"


def test_support_requires_supported_move_to_exact_target(tmp_path: Path) -> None:
    """Support is invalid when the named fleet moves somewhere else."""
    nodes = support_nodes("A", "B", "E", "F", "G")
    fleets = [
        fleet("amber-m", "amber", "A"),
        fleet("amber-s", "amber", "B"),
        fleet("cobalt-h", "cobalt", "G"),
    ]
    match = make_match(
        players=support_players(),
        nodes=nodes,
        edges=complete_edges("A", "B", "E", "F", "G"),
        fleets=fleets,
        orders=[move(1, "amber-m", "E"), support(1, "amber-s", "amber-m", "F")],
    )
    proc, _, payload = run_case(tmp_path, match)
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-s")["status"] == "support-invalid"


def test_support_requires_supported_move_to_be_edge_legal(tmp_path: Path) -> None:
    """An edge-blocked move cannot receive active support."""
    nodes = support_nodes("A", "B", "E", "F")
    fleets = [
        fleet("amber-m", "amber", "A"),
        fleet("amber-s", "amber", "B"),
        fleet("cobalt-h", "cobalt", "F"),
    ]
    match = make_match(
        players=support_players(),
        nodes=nodes,
        edges=[{"a": "B", "b": "E"}, {"a": "A", "b": "F"}],
        fleets=fleets,
        orders=[move(1, "amber-m", "E"), support(1, "amber-s", "amber-m", "E")],
    )
    proc, _, payload = run_case(tmp_path, match)
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-m")["status"] == "blocked-edge"
    assert fleet_row(payload, "amber-s")["status"] == "support-invalid"


def test_support_requires_supported_move_to_be_depth_legal(tmp_path: Path) -> None:
    """A depth-blocked move cannot gain strength from a nominal supporter."""
    nodes = support_nodes("A", "B", "E", "F")
    next(node for node in nodes if node["id"] == "E")["base_depth_m"] = 0.5
    fleets = [
        fleet("amber-m", "amber", "A", draft=1.0),
        fleet("amber-s", "amber", "B", draft=0.5),
        fleet("cobalt-h", "cobalt", "F", draft=0.5),
    ]
    match = make_match(
        players=support_players(),
        nodes=nodes,
        edges=complete_edges("A", "B", "E", "F"),
        fleets=fleets,
        orders=[move(1, "amber-m", "E"), support(1, "amber-s", "amber-m", "E")],
    )
    proc, _, payload = run_case(tmp_path, match)
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-m")["status"] == "blocked-depth"
    assert fleet_row(payload, "amber-s")["status"] == "support-invalid"


def test_supporter_draft_at_exact_depth_boundary_is_valid(tmp_path: Path) -> None:
    """Support accepts a draft exactly equal to both rounded effective depths."""
    nodes = support_nodes("A", "B", "E", "F")
    fleets = [
        fleet("amber-m", "amber", "A", draft=0.5),
        fleet("amber-s", "amber", "B", draft=1.0),
        fleet("cobalt-h", "cobalt", "F", draft=0.5),
    ]
    match = make_match(
        players=support_players(),
        nodes=nodes,
        edges=complete_edges("A", "B", "E", "F"),
        fleets=fleets,
        orders=[move(1, "amber-m", "E"), support(1, "amber-s", "amber-m", "E")],
    )
    proc, _, payload = run_case(tmp_path, match)
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-s")["status"] == "supported"


def test_supporter_depth_rounding_can_invalidate_support(tmp_path: Path) -> None:
    """Support depth checks use the six-decimal rounded target depth."""
    nodes = support_nodes("A", "B", "E", "F")
    next(node for node in nodes if node["id"] == "E")["base_depth_m"] = 0.9999994
    fleets = [
        fleet("amber-m", "amber", "A", draft=0.5),
        fleet("amber-s", "amber", "B", draft=1.0),
        fleet("cobalt-h", "cobalt", "F", draft=0.5),
    ]
    match = make_match(
        players=support_players(),
        nodes=nodes,
        edges=complete_edges("A", "B", "E", "F"),
        fleets=fleets,
        orders=[move(1, "amber-m", "E"), support(1, "amber-s", "amber-m", "E")],
    )
    proc, _, payload = run_case(tmp_path, match)
    assert proc.returncode == 0, proc.stderr
    assert node_row(payload, "E")["effective_depth_m"] == 0.999999
    assert fleet_row(payload, "amber-m")["status"] == "moved"
    assert fleet_row(payload, "amber-s")["status"] == "support-invalid"


def test_single_support_outweighs_higher_initiative(tmp_path: Path) -> None:
    """Strength from one active support outranks an unsupported initiative lead."""
    nodes = support_nodes("A", "B", "C", "E")
    fleets = [
        fleet("amber-m", "amber", "A"),
        fleet("amber-s", "amber", "B"),
        fleet("cobalt-m", "cobalt", "C"),
    ]
    match = make_match(
        players=support_players(amber_initiative=1, cobalt_initiative=99),
        nodes=nodes,
        edges=complete_edges("A", "B", "C", "E"),
        fleets=fleets,
        orders=[
            move(1, "amber-m", "E"),
            support(1, "amber-s", "amber-m", "E"),
            move(1, "cobalt-m", "E"),
        ],
    )
    proc, _, payload = run_case(tmp_path, match)
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-m")["status"] == "moved"
    assert fleet_row(payload, "cobalt-m")["status"] == "blocked-contest"


def test_multiple_supports_accumulate_for_one_move(tmp_path: Path) -> None:
    """Every active uncut supporter adds one unit of contest strength."""
    ids = ("A", "B", "C", "D", "E", "F")
    fleets = [
        fleet("amber-m", "amber", "A"),
        fleet("amber-s1", "amber", "B"),
        fleet("amber-s2", "amber", "D"),
        fleet("cobalt-m", "cobalt", "C"),
        fleet("cobalt-s", "cobalt", "F"),
    ]
    match = make_match(
        players=support_players(amber_initiative=1, cobalt_initiative=99),
        nodes=support_nodes(*ids),
        edges=complete_edges(*ids),
        fleets=fleets,
        orders=[
            move(1, "amber-m", "E"),
            support(1, "amber-s1", "amber-m", "E"),
            support(1, "amber-s2", "amber-m", "E"),
            move(1, "cobalt-m", "E"),
            support(1, "cobalt-s", "cobalt-m", "E"),
        ],
    )
    proc, _, payload = run_case(tmp_path, match)
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-m")["status"] == "moved"
    assert fleet_row(payload, "cobalt-m")["status"] == "blocked-contest"


def test_equal_supported_strength_uses_existing_tie_break_chain(tmp_path: Path) -> None:
    """Equal supported strength falls through initiative, player ID, then fleet ID."""
    ids = ("A", "B", "C", "D", "E", "F", "G", "H")
    nodes = support_nodes(*ids)
    edges = complete_edges(*ids)

    initiative_match = make_match(
        players=support_players(amber_initiative=2, cobalt_initiative=3),
        nodes=nodes,
        edges=edges,
        fleets=[
            fleet("amber-m", "amber", "A"),
            fleet("amber-s", "amber", "B"),
            fleet("cobalt-m", "cobalt", "C"),
            fleet("cobalt-s", "cobalt", "D"),
        ],
        orders=[
            move(1, "amber-m", "E"),
            support(1, "amber-s", "amber-m", "E"),
            move(1, "cobalt-m", "E"),
            support(1, "cobalt-s", "cobalt-m", "E"),
        ],
    )
    proc, _, payload = run_case(tmp_path / "initiative", initiative_match)
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "cobalt-m")["status"] == "moved"

    player_match = copy.deepcopy(initiative_match)
    player_match["players"] = [
        {"id": "amber", "initiative": 3},
        {"id": "cobalt", "initiative": 3},
    ]
    proc, _, payload = run_case(tmp_path / "player", player_match)
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-m")["status"] == "moved"

    fleet_match = make_match(
        players=support_players(amber_initiative=3, cobalt_initiative=0),
        nodes=nodes,
        edges=edges,
        fleets=[
            fleet("amber-a", "amber", "A"),
            fleet("amber-z", "amber", "B"),
            fleet("amber-sa", "amber", "C"),
            fleet("amber-sz", "amber", "D"),
            fleet("cobalt-h", "cobalt", "H"),
        ],
        orders=[
            move(1, "amber-a", "E"),
            move(1, "amber-z", "E"),
            support(1, "amber-sa", "amber-a", "E"),
            support(1, "amber-sz", "amber-z", "E"),
        ],
    )
    proc, _, payload = run_case(tmp_path / "fleet", fleet_match)
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-a")["status"] == "moved"
    assert fleet_row(payload, "amber-z")["status"] == "blocked-contest"


def test_enemy_candidate_cuts_support_even_when_it_loses_contest(tmp_path: Path) -> None:
    """A candidate enemy attack cuts support before losing its own target contest."""
    ids = ("A", "B", "D", "E", "F", "G")
    fleets = [
        fleet("amber-m", "amber", "A"),
        fleet("amber-s", "amber", "B"),
        fleet("amber-def", "amber", "F"),
        fleet("cobalt-a", "cobalt", "D"),
        fleet("cobalt-h", "cobalt", "G"),
    ]
    match = make_match(
        players=support_players(amber_initiative=9, cobalt_initiative=1),
        nodes=support_nodes(*ids),
        edges=complete_edges(*ids),
        fleets=fleets,
        orders=[
            move(1, "amber-m", "E"),
            support(1, "amber-s", "amber-m", "E"),
            move(1, "amber-def", "B"),
            move(1, "cobalt-a", "B"),
        ],
    )
    proc, _, payload = run_case(tmp_path, match)
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "cobalt-a")["status"] == "blocked-contest"
    assert fleet_row(payload, "amber-s")["status"] == "support-cut"


def test_enemy_candidate_cuts_support_even_when_blocked_occupied(tmp_path: Path) -> None:
    """An enemy move blocked by the holding supporter still cuts that support."""
    ids = ("A", "B", "D", "E", "F")
    fleets = [
        fleet("amber-m", "amber", "A"),
        fleet("amber-s", "amber", "B"),
        fleet("cobalt-a", "cobalt", "D"),
        fleet("cobalt-h", "cobalt", "F"),
    ]
    match = make_match(
        players=support_players(),
        nodes=support_nodes(*ids),
        edges=complete_edges(*ids),
        fleets=fleets,
        orders=[
            move(1, "amber-m", "E"),
            support(1, "amber-s", "amber-m", "E"),
            move(1, "cobalt-a", "B"),
        ],
    )
    proc, _, payload = run_case(tmp_path, match)
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "cobalt-a")["status"] == "blocked-occupied"
    assert fleet_row(payload, "amber-s")["status"] == "support-cut"


def test_edge_blocked_attack_does_not_cut_support(tmp_path: Path) -> None:
    """An attack that fails adjacency never reaches candidacy and cannot cut support."""
    ids = ("A", "B", "D", "E", "F")
    edges = [
        {"a": "A", "b": "E"},
        {"a": "B", "b": "E"},
        {"a": "D", "b": "F"},
    ]
    fleets = [
        fleet("amber-m", "amber", "A"),
        fleet("amber-s", "amber", "B"),
        fleet("cobalt-a", "cobalt", "D"),
        fleet("cobalt-h", "cobalt", "F"),
    ]
    match = make_match(
        players=support_players(),
        nodes=support_nodes(*ids),
        edges=edges,
        fleets=fleets,
        orders=[
            move(1, "amber-m", "E"),
            support(1, "amber-s", "amber-m", "E"),
            move(1, "cobalt-a", "B"),
        ],
    )
    proc, _, payload = run_case(tmp_path, match)
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "cobalt-a")["status"] == "blocked-edge"
    assert fleet_row(payload, "amber-s")["status"] == "supported"


def test_depth_blocked_attack_does_not_cut_support(tmp_path: Path) -> None:
    """An enemy move failing rounded source depth cannot cut active support."""
    ids = ("A", "B", "D", "E", "F")
    nodes = support_nodes(*ids)
    next(node for node in nodes if node["id"] == "D")["base_depth_m"] = 0.5
    fleets = [
        fleet("amber-m", "amber", "A", draft=0.5),
        fleet("amber-s", "amber", "B", draft=0.5),
        fleet("cobalt-a", "cobalt", "D", draft=1.0),
        fleet("cobalt-h", "cobalt", "F", draft=0.5),
    ]
    match = make_match(
        players=support_players(),
        nodes=nodes,
        edges=complete_edges(*ids),
        fleets=fleets,
        orders=[
            move(1, "amber-m", "E"),
            support(1, "amber-s", "amber-m", "E"),
            move(1, "cobalt-a", "B"),
        ],
    )
    proc, _, payload = run_case(tmp_path, match)
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "cobalt-a")["status"] == "blocked-depth"
    assert fleet_row(payload, "amber-s")["status"] == "supported"


def test_same_player_candidate_does_not_cut_support(tmp_path: Path) -> None:
    """Only an otherwise legal candidate owned by another player cuts support."""
    ids = ("A", "B", "D", "E", "F")
    fleets = [
        fleet("amber-m", "amber", "A"),
        fleet("amber-s", "amber", "B"),
        fleet("amber-a", "amber", "D"),
        fleet("cobalt-h", "cobalt", "F"),
    ]
    match = make_match(
        players=support_players(),
        nodes=support_nodes(*ids),
        edges=complete_edges(*ids),
        fleets=fleets,
        orders=[
            move(1, "amber-m", "E"),
            support(1, "amber-s", "amber-m", "E"),
            move(1, "amber-a", "B"),
        ],
    )
    proc, _, payload = run_case(tmp_path, match)
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-a")["status"] == "blocked-occupied"
    assert fleet_row(payload, "amber-s")["status"] == "supported"


def test_cut_support_changes_contest_winner_and_summary_digest(tmp_path: Path) -> None:
    """Cutting support changes strength, contest outcome, statuses, and the digest."""
    ids = ("A", "B", "C", "D", "E")
    fleets = [
        fleet("amber-m", "amber", "A"),
        fleet("amber-s", "amber", "B"),
        fleet("cobalt-m", "cobalt", "C"),
        fleet("cobalt-a", "cobalt", "D"),
    ]
    common_orders = [
        move(1, "amber-m", "E"),
        support(1, "amber-s", "amber-m", "E"),
        move(1, "cobalt-m", "E"),
    ]
    base = make_match(
        match_id="uncut",
        players=support_players(amber_initiative=1, cobalt_initiative=9),
        nodes=support_nodes(*ids),
        edges=complete_edges(*ids),
        fleets=fleets,
        orders=common_orders,
    )
    proc, _, uncut = run_case(tmp_path / "uncut", base)
    assert proc.returncode == 0, proc.stderr

    cut_match = copy.deepcopy(base)
    cut_match["match_id"] = "cut"
    cut_match["orders"] = common_orders + [move(1, "cobalt-a", "B")]
    proc, _, cut = run_case(tmp_path / "cut", cut_match)
    assert proc.returncode == 0, proc.stderr

    assert fleet_row(uncut, "amber-m")["status"] == "moved"
    assert fleet_row(cut, "cobalt-m")["status"] == "moved"
    assert fleet_row(cut, "amber-s")["status"] == "support-cut"
    assert uncut["summary"]["sha256"] == expected_digest(uncut)
    assert cut["summary"]["sha256"] == expected_digest(cut)
    assert uncut["summary"]["sha256"] != cut["summary"]["sha256"]


def test_supported_contest_winner_can_still_be_blocked_by_stationary_occupant(
    tmp_path: Path,
) -> None:
    """Support chooses the contender but does not bypass occupancy dependencies."""
    ids = ("A", "B", "C", "E")
    fleets = [
        fleet("amber-m", "amber", "A"),
        fleet("amber-s", "amber", "B"),
        fleet("cobalt-m", "cobalt", "C"),
        fleet("cobalt-h", "cobalt", "E"),
    ]
    match = make_match(
        players=support_players(amber_initiative=1, cobalt_initiative=9),
        nodes=support_nodes(*ids),
        edges=complete_edges(*ids),
        fleets=fleets,
        orders=[
            move(1, "amber-m", "E"),
            support(1, "amber-s", "amber-m", "E"),
            move(1, "cobalt-m", "E"),
        ],
    )
    proc, _, payload = run_case(tmp_path, match)
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-s")["status"] == "supported"
    assert fleet_row(payload, "amber-m")["status"] == "blocked-occupied"
    assert fleet_row(payload, "cobalt-m")["status"] == "blocked-contest"


def test_supported_winner_vacates_and_unlocks_dependency_chain(tmp_path: Path) -> None:
    """A supported winner and a vacating occupant succeed as one dependency chain."""
    ids = ("A", "B", "C", "E", "F")
    fleets = [
        fleet("amber-m", "amber", "A"),
        fleet("amber-s", "amber", "B"),
        fleet("amber-chain", "amber", "E"),
        fleet("cobalt-m", "cobalt", "C"),
    ]
    match = make_match(
        players=support_players(amber_initiative=1, cobalt_initiative=9),
        nodes=support_nodes(*ids),
        edges=complete_edges(*ids),
        fleets=fleets,
        orders=[
            move(1, "amber-m", "E"),
            support(1, "amber-s", "amber-m", "E"),
            move(1, "amber-chain", "F"),
            move(1, "cobalt-m", "E"),
        ],
    )
    proc, _, payload = run_case(tmp_path, match)
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-m")["node_id"] == "E"
    assert fleet_row(payload, "amber-m")["status"] == "moved"
    assert fleet_row(payload, "amber-chain")["node_id"] == "F"
    assert fleet_row(payload, "amber-chain")["status"] == "moved"
    assert fleet_row(payload, "cobalt-m")["status"] == "blocked-contest"


def test_multiturn_support_uses_current_positions_and_preserves_scoring(
    tmp_path: Path,
) -> None:
    """Later support adjacency uses moved positions while retained territory keeps scoring."""
    ids = ("A", "B", "C", "D", "E", "F")
    nodes = support_nodes(*ids)
    edges = [
        {"a": "A", "b": "D"},
        {"a": "B", "b": "C"},
        {"a": "C", "b": "E"},
        {"a": "D", "b": "E"},
    ]
    fleets = [
        fleet("amber-m", "amber", "A"),
        fleet("amber-s", "amber", "B"),
        fleet("cobalt-h", "cobalt", "F"),
    ]
    match = make_match(
        players=support_players(),
        nodes=nodes,
        edges=edges,
        fleets=fleets,
        turn_count=2,
        orders=[
            move(1, "amber-m", "D"),
            move(1, "amber-s", "C"),
            move(2, "amber-m", "E"),
            support(2, "amber-s", "amber-m", "E"),
        ],
    )
    proc, _, payload = run_case(tmp_path, match)
    assert proc.returncode == 0, proc.stderr
    assert fleet_row(payload, "amber-s", turn=2)["node_id"] == "C"
    assert fleet_row(payload, "amber-s", turn=2)["status"] == "supported"
    assert fleet_row(payload, "amber-m", turn=2)["node_id"] == "E"
    assert owner_map(payload["turns"][1]["nodes"])["D"] == "amber"
    assert score_map(payload["turns"][0]["score_delta"]) == {"amber": 7, "cobalt": 6}
    assert score_map(payload["turns"][1]["score_delta"]) == {"amber": 12, "cobalt": 6}
    assert score_map(payload["turns"][1]["scores"]) == {"amber": 19, "cobalt": 12}


def test_support_scenario_is_invariant_to_input_order_threads_and_cwd(
    tmp_path: Path,
) -> None:
    """Combined support, cutting, contests, capture, and digest stay byte deterministic."""
    ids = ("A", "B", "C", "D", "E", "F", "G")
    match = make_match(
        match_id="support-invariance",
        players=support_players(amber_initiative=2, cobalt_initiative=5),
        nodes=support_nodes(*ids),
        edges=complete_edges(*ids),
        fleets=[
            fleet("amber-m", "amber", "A"),
            fleet("amber-s1", "amber", "B"),
            fleet("amber-s2", "amber", "F"),
            fleet("cobalt-m", "cobalt", "C"),
            fleet("cobalt-a", "cobalt", "D"),
            fleet("cobalt-s", "cobalt", "G"),
        ],
        orders=[
            move(1, "amber-m", "E"),
            support(1, "amber-s1", "amber-m", "E"),
            support(1, "amber-s2", "amber-m", "E"),
            move(1, "cobalt-m", "E"),
            support(1, "cobalt-s", "cobalt-m", "E"),
            move(1, "cobalt-a", "B"),
        ],
    )
    variants: list[bytes] = []
    for index, threads in enumerate((1, 2, 7, 3)):
        shuffled = copy.deepcopy(match)
        rng = random.Random(7319 + index)
        for key in ("players", "nodes", "edges", "fleets", "orders"):
            rng.shuffle(shuffled[key])
        cwd = tmp_path / f"cwd-{index}"
        cwd.mkdir()
        proc, output, payload = run_case(
            tmp_path / f"case-{index}",
            shuffled,
            threads=threads,
            cwd=cwd,
        )
        assert proc.returncode == 0, proc.stderr
        assert payload["summary"]["sha256"] == expected_digest(payload)
        variants.append(output.read_bytes())
    assert len(set(variants)) == 1
