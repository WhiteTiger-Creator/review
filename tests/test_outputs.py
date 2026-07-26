#!/usr/bin/env python3
"""Verifier for Opaline Dungeon Route Cartographer."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path

import pytest
from reference_model import (
    ALL_MOVES,
    CRUMBLE,
    DOOR,
    EXIT,
    FLOOR,
    KEY,
    MOVE_DOWN,
    MOVE_LEFT,
    MOVE_RIGHT,
    PORTAL,
    START,
    STATUS_INVALID_INPUT,
    STATUS_SOLVED,
    STATUS_UNSOLVABLE,
    VAL_INVALID_ANALYSIS,
    VAL_INVALID_INPUT,
    VAL_VALID,
    WALL,
    analyze_board,
    board,
    tile,
)

APP = Path("/app/opaline")
HARNESS_DIR = Path("/tests/harness")
BUILD_DIR = Path("/tmp/opaline-harness-build")


def _f() -> dict:
    return tile(FLOOR)


def _w() -> dict:
    return tile(WALL)


def _s() -> dict:
    return tile(START)


def _e() -> dict:
    return tile(EXIT)


def _k(tag: str) -> dict:
    return tile(KEY, tag)


def _d(tag: str) -> dict:
    return tile(DOOR, tag)


def _c() -> dict:
    return tile(CRUMBLE)


def _p(tag: str) -> dict:
    return tile(PORTAL, tag)


@pytest.fixture(scope="session")
def harness_bin() -> Path:
    """Build the public module and verifier harness once offline."""
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True)
    shutil.copytree(HARNESS_DIR, BUILD_DIR, dirs_exist_ok=True)
    env = os.environ.copy()
    env["GOPROXY"] = "off"
    env["GOSUMDB"] = "off"
    env["GOWORK"] = "off"
    env["GOCACHE"] = str(BUILD_DIR / "go-cache")
    env["GOMODCACHE"] = str(BUILD_DIR / "mod-cache")
    # Ensure replace path exists
    go_mod = (BUILD_DIR / "go.mod").read_text()
    assert "opaline/cartographer" in go_mod
    proc = subprocess.run(
        ["go", "build", "-o", str(BUILD_DIR / "harness"), "."],
        cwd=BUILD_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.fail(f"harness build failed:\n{proc.stdout}\n{proc.stderr}")
    bin_path = BUILD_DIR / "harness"
    assert bin_path.is_file()
    return bin_path


def call_harness(harness_bin: Path, payload: dict) -> dict:
    proc = subprocess.run(
        [str(harness_bin)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={**os.environ, "GOPROXY": "off", "GOSUMDB": "off"},
        check=False,
    )
    if proc.returncode != 0:
        pytest.fail(f"harness exit {proc.returncode}: {proc.stderr}\n{proc.stdout}")
    data = json.loads(proc.stdout)
    if data.get("error"):
        pytest.fail(data["error"])
    assert data.get("board_unchanged") is True
    return data


def analyze(harness_bin: Path, b: dict) -> dict:
    data = call_harness(harness_bin, {"op": "analyze", "board": b})
    return data["analysis"]


def validate(harness_bin: Path, b: dict, candidate: dict) -> int:
    data = call_harness(
        harness_bin, {"op": "validate", "board": b, "candidate": candidate}
    )
    return int(data["validation"])


def assert_match(got: dict, expected: dict) -> None:
    assert got["status"] == expected["status"]
    assert got["distance"] == expected["distance"]
    assert got["shortest_count"] == expected["shortest_count"]
    assert got["canonical_moves"] == expected["canonical_moves"]
    assert got["trace"] == expected["trace"]
    assert got["mandatory_landings"] == expected["mandatory_landings"]
    assert got["decision_points"] == expected["decision_points"]
    assert got["canonical_moves"] is not None
    assert got["trace"] is not None
    assert got["mandatory_landings"] is not None
    assert got["decision_points"] is not None


def test_public_module_and_harness_compile_offline(harness_bin: Path) -> None:
    """The Go library and verifier harness build offline with the exact package, exported types, constants, fields, and function signatures."""
    assert harness_bin.is_file()
    sources = "\n".join(p.read_text() for p in APP.glob("*.go"))
    for name in (
        "type Coord struct",
        "TileFloor",
        "TilePortal",
        "MoveUp",
        "StatusSolved",
        "StatusNotImplemented",
        "type TraceStep struct",
        "type MandatoryLanding struct",
        "type DecisionPoint struct",
        "type Analysis struct",
        "ValidationValid",
        "func Analyze(",
        "func Validate(",
    ):
        assert name in sources
    mod = (APP / "go.mod").read_text()
    assert "module opaline/cartographer" in mod
    # Compile package offline again
    env = {**os.environ, "GOPROXY": "off", "GOSUMDB": "off", "GOWORK": "off"}
    proc = subprocess.run(
        ["go", "vet", "./..."],
        cwd=APP,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr


def test_environment_remains_library_only() -> None:
    """The public module remains a level-analysis library with no renderer, generator, parser, interactive game, server, filesystem access, or executable package."""
    go_files = list(APP.rglob("*.go"))
    assert go_files
    for path in go_files:
        text = path.read_text()
        assert "package main" not in text
        for banned in (
            "os.Open",
            "os.ReadFile",
            "os.WriteFile",
            "os.Getenv",
            "http.Listen",
            "exec.Command",
            "net.Listen",
        ):
            assert banned not in text, f"{path} contains {banned}"
    assert not (APP / "main.go").exists()


def test_straight_floor_corridor_unique_route(harness_bin: Path) -> None:
    """A straight floor corridor returns its unique shortest route, count, trace, and unanimous landings."""
    b = board(1, 3, [_s(), _f(), _e()])  # invalid rows=1
    # use 2x3 with wall row
    b = board(2, 3, [_s(), _f(), _e(), _w(), _w(), _w()])
    exp = analyze_board(b)
    got = analyze(harness_bin, b)
    assert_match(got, exp)
    assert got["status"] == STATUS_SOLVED
    assert got["shortest_count"] == "1"
    assert len(got["mandatory_landings"]) == got["distance"]


def test_walls_force_shortest_detour(harness_bin: Path) -> None:
    """Walls force the independently verified shortest detour without admitting illegal steps."""
    # S . E
    # . # .
    # . . .
    b = board(
        3,
        3,
        [
            _s(),
            _f(),
            _e(),
            _f(),
            _w(),
            _f(),
            _f(),
            _f(),
            _f(),
        ],
    )
    exp = analyze_board(b)
    got = analyze(harness_bin, b)
    assert_match(got, exp)
    assert got["distance"] == 2
    # Direct right from start hits... start(0,0) right (0,1) right (0,2)=exit. Distance 2, wall doesn't block top.
    # Need wall blocking top path:
    b = board(
        3,
        3,
        [
            _s(),
            _w(),
            _e(),
            _f(),
            _f(),
            _f(),
            _f(),
            _f(),
            _f(),
        ],
    )
    exp = analyze_board(b)
    got = analyze(harness_bin, b)
    assert_match(got, exp)
    assert got["distance"] > 2
    assert all(m in ALL_MOVES for m in got["canonical_moves"])


def test_lexicographically_smallest_among_equal_routes(harness_bin: Path) -> None:
    """Equal-length routes choose the lexicographically smallest sequence under Up, Right, Down, Left."""
    # S .
    # . E
    b = board(2, 2, [_s(), _f(), _f(), _e()])
    exp = analyze_board(b)
    got = analyze(harness_bin, b)
    assert_match(got, exp)
    assert got["canonical_moves"] == [MOVE_RIGHT, MOVE_DOWN]
    assert got["shortest_count"] == "2"


def test_counts_distinct_sequences_sharing_later_state(harness_bin: Path) -> None:
    """Several shortest move sequences are counted exactly even when they reach the same later state."""
    b = board(2, 2, [_s(), _f(), _f(), _e()])
    exp = analyze_board(b)
    got = analyze(harness_bin, b)
    assert_match(got, exp)
    assert int(got["shortest_count"]) == 2


def test_key_enables_matching_door(harness_bin: Path) -> None:
    """Entering a key enables its matching door on subsequent moves."""
    # S a
    # D E
    b = board(2, 2, [_s(), _k("a"), _d("a"), _e()])
    exp = analyze_board(b)
    got = analyze(harness_bin, b)
    assert_match(got, exp)
    assert got["status"] == STATUS_SOLVED
    assert "a" in got["trace"][-1]["keys"]


def test_key_persists_through_portals_crumbles_and_floors(harness_bin: Path) -> None:
    """A collected key persists through portals, crumble departures, and revisited ordinary floor."""
    # S a C .
    # # # # Pa
    # . Pb D E
    b = board(
        3,
        4,
        [
            _s(),
            _k("a"),
            _c(),
            _f(),
            _w(),
            _w(),
            _w(),
            _p("a"),
            _f(),
            _p("a"),
            _d("a"),
            _e(),
        ],
    )
    exp = analyze_board(b)
    got = analyze(harness_bin, b)
    assert_match(got, exp)
    assert got["status"] == STATUS_SOLVED
    assert "a" in got["trace"][-1]["keys"]


def test_unreachable_key_makes_door_unsolvable(harness_bin: Path) -> None:
    """A door whose key cannot be reached makes the exit unsolvable when it blocks every route."""
    # S #
    # D E   key absent / unreachable
    b = board(2, 2, [_s(), _w(), _d("a"), _e()])
    exp = analyze_board(b)
    got = analyze(harness_bin, b)
    assert_match(got, exp)
    assert got["status"] == STATUS_UNSOLVABLE
    assert got["distance"] == -1
    assert got["shortest_count"] == "0"


def test_crumble_collapses_after_departure(harness_bin: Path) -> None:
    """Leaving a crumble tile collapses it after the successful move and prevents later re-entry."""
    # S C E
    # . . .
    b = board(2, 3, [_s(), _c(), _e(), _f(), _f(), _f()])
    exp = analyze_board(b)
    got = analyze(harness_bin, b)
    assert_match(got, exp)
    assert got["status"] == STATUS_SOLVED
    # Canonical prefers up... from (0,0) right onto crumble then right to exit.
    assert any(step["collapsed"] for step in got["trace"])


def test_collapsed_set_distinguishes_states(harness_bin: Path) -> None:
    """Identical coordinates with different collapsed sets remain distinct states and produce the correct solvability and count."""
    # S C .
    # C # E
    # . . .
    b = board(
        3,
        3,
        [
            _s(),
            _c(),
            _f(),
            _c(),
            _w(),
            _e(),
            _f(),
            _f(),
            _f(),
        ],
    )
    exp = analyze_board(b)
    got = analyze(harness_bin, b)
    assert_match(got, exp)
    assert got["status"] == STATUS_SOLVED


def test_portal_consumes_one_move_to_partner(harness_bin: Path) -> None:
    """Entering a portal consumes one move and traces the paired endpoint as the landing coordinate."""
    # S Pa
    # # #
    # Pb E
    b = board(3, 2, [_s(), _p("a"), _w(), _w(), _p("a"), _e()])
    exp = analyze_board(b)
    got = analyze(harness_bin, b)
    assert_match(got, exp)
    assert got["status"] == STATUS_SOLVED
    # First move right enters portal, lands on partner
    assert got["trace"][0]["to"] == {"row": 2, "col": 0}


def test_portal_shortcut_competes_with_ordinary_route(harness_bin: Path) -> None:
    """A portal shortcut competes correctly with an ordinary route under shortest distance and canonical move order."""
    # S . .
    # Pa # .
    # . Pb E
    b = board(
        3,
        3,
        [
            _s(),
            _f(),
            _f(),
            _p("a"),
            _w(),
            _f(),
            _f(),
            _p("a"),
            _e(),
        ],
    )
    exp = analyze_board(b)
    got = analyze(harness_bin, b)
    assert_match(got, exp)
    assert got["status"] == STATUS_SOLVED


def test_combined_key_door_crumble_portal_level(harness_bin: Path) -> None:
    """A combined key, door, crumble, and portal level matches the independent complete-state route analysis."""
    b = board(
        4,
        4,
        [
            _s(),
            _k("a"),
            _c(),
            _p("a"),
            _f(),
            _w(),
            _w(),
            _f(),
            _f(),
            _d("a"),
            _f(),
            _p("a"),
            _f(),
            _f(),
            _c(),
            _e(),
        ],
    )
    exp = analyze_board(b)
    got = analyze(harness_bin, b)
    assert_match(got, exp)


def test_canonical_trace_reports_complete_sorted_state(harness_bin: Path) -> None:
    """Every canonical trace step reports exact indices, moves, from/to coordinates, sorted held keys, and sorted cumulative collapses."""
    b = board(
        3,
        4,
        [
            _s(),
            _k("b"),
            _k("a"),
            _c(),
            _f(),
            _f(),
            _f(),
            _c(),
            _f(),
            _f(),
            _f(),
            _e(),
        ],
    )
    exp = analyze_board(b)
    got = analyze(harness_bin, b)
    assert_match(got, exp)
    for i, step in enumerate(got["trace"], start=1):
        assert step["index"] == i
        assert step["keys"] == sorted(step["keys"])
        cols = step["collapsed"]
        assert cols == sorted(cols, key=lambda c: (c["row"], c["col"]))


def test_mandatory_landings_only_same_step_coords(harness_bin: Path) -> None:
    """Mandatory landings include only coordinates shared at the same step by every shortest route."""
    b = board(2, 2, [_s(), _f(), _f(), _e()])
    exp = analyze_board(b)
    got = analyze(harness_bin, b)
    assert_match(got, exp)
    # Step1 splits between (0,1) and (1,0); step2 both at exit.
    steps = {l["step"]: l["at"] for l in got["mandatory_landings"]}
    assert 1 not in steps
    assert steps[2] == {"row": 1, "col": 1}


def test_split_then_rejoin_landings(harness_bin: Path) -> None:
    """Routes that split and later rejoin produce nonmandatory branch landings followed by mandatory merged landings."""
    # S . E
    # . . .
    b = board(2, 3, [_s(), _f(), _e(), _f(), _f(), _f()])
    exp = analyze_board(b)
    got = analyze(harness_bin, b)
    assert_match(got, exp)
    mandatory_steps = [l["step"] for l in got["mandatory_landings"]]
    assert got["distance"] in mandatory_steps  # exit landing unanimous


def test_decision_points_list_shortest_winning_alternatives(harness_bin: Path) -> None:
    """Decision points on the canonical route list every and only shortest-winning next move from that exact complete state."""
    b = board(2, 2, [_s(), _f(), _f(), _e()])
    exp = analyze_board(b)
    got = analyze(harness_bin, b)
    assert_match(got, exp)
    assert got["decision_points"]
    dp0 = got["decision_points"][0]
    assert dp0["step"] == 1
    assert dp0["alternatives"] == [MOVE_RIGHT, MOVE_DOWN]


def test_distinct_prefixes_contribute_to_count(harness_bin: Path) -> None:
    """Distinct move prefixes that converge on one state still contribute separately to the arbitrary-precision shortest count."""
    # Open 3x3 corner to corner: C(4,2)=6
    b = board(
        3,
        3,
        [
            _s(),
            _f(),
            _f(),
            _f(),
            _f(),
            _f(),
            _f(),
            _f(),
            _e(),
        ],
    )
    exp = analyze_board(b)
    got = analyze(harness_bin, b)
    assert_match(got, exp)
    assert got["shortest_count"] == "6"


def test_unsolvable_canonical_shape(harness_bin: Path) -> None:
    """A valid unsolvable board returns the exact canonical negative-distance and non-nil empty-slice shape."""
    b = board(2, 2, [_s(), _w(), _w(), _e()])
    exp = analyze_board(b)
    got = analyze(harness_bin, b)
    assert_match(got, exp)
    assert got["status"] == STATUS_UNSOLVABLE
    assert got["distance"] == -1
    assert got["shortest_count"] == "0"
    assert got["canonical_moves"] == []
    assert got["trace"] == []
    assert got["mandatory_landings"] == []
    assert got["decision_points"] == []


def test_validate_accepts_exact_solved_and_unsolvable(harness_bin: Path) -> None:
    """Validate accepts exact solved and unsolvable analyses."""
    solved_b = board(2, 2, [_s(), _f(), _f(), _e()])
    solved = analyze_board(solved_b)
    assert validate(harness_bin, solved_b, solved) == VAL_VALID
    hard_b = board(2, 2, [_s(), _w(), _w(), _e()])
    hard = analyze_board(hard_b)
    assert validate(harness_bin, hard_b, hard) == VAL_VALID


def test_validate_rejects_forged_and_malformed_candidates(harness_bin: Path) -> None:
    """Validation rejects forged distance or count, noncanonical moves, illegal routes, incomplete trace state, false landings, missing alternatives, nil slices, and wrong ordering."""
    b = board(2, 2, [_s(), _f(), _f(), _e()])
    good = analyze_board(b)
    forged = dict(good)
    forged["distance"] = good["distance"] + 1
    assert validate(harness_bin, b, forged) == VAL_INVALID_ANALYSIS
    forged = dict(good)
    forged["shortest_count"] = "99"
    assert validate(harness_bin, b, forged) == VAL_INVALID_ANALYSIS
    forged = dict(good)
    forged["canonical_moves"] = [MOVE_DOWN, MOVE_RIGHT]  # noncanonical
    assert validate(harness_bin, b, forged) == VAL_INVALID_ANALYSIS
    forged = dict(good)
    forged["mandatory_landings"] = [{"step": 1, "at": {"row": 0, "col": 1}}]
    assert validate(harness_bin, b, forged) == VAL_INVALID_ANALYSIS
    forged = dict(good)
    forged["decision_points"] = []
    assert validate(harness_bin, b, forged) == VAL_INVALID_ANALYSIS


def test_determinism_ownership_concurrency(harness_bin: Path) -> None:
    """Repeated and concurrent calls are identical, leave board tiles unchanged, and return independently owned slices."""
    b = board(2, 2, [_s(), _f(), _f(), _e()])
    results = []

    def worker() -> None:
        results.append(analyze(harness_bin, b))

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == 4
    for r in results[1:]:
        assert_match(r, results[0])
    # Mutating one result must not affect another
    results[0]["canonical_moves"].append(MOVE_LEFT)
    assert results[1]["canonical_moves"][-1] != MOVE_LEFT


def test_invalid_dimensions_tiles_kinds_tags(harness_bin: Path) -> None:
    """Invalid dimensions, tile counts, start/exit multiplicity, kinds, and ordinary-tile tags return canonical invalid input."""
    cases = [
        board(1, 2, [_s(), _e()]),
        board(2, 2, [_s(), _e()]),  # wrong tile count
        board(2, 2, [_s(), _f(), _f(), _f()]),  # no exit
        board(2, 2, [_s(), _s(), _e(), _f()]),  # two starts
        board(2, 2, [_s(), _f(), _f(), tile(99)]),
        board(2, 2, [_s(), tile(FLOOR, "x"), _f(), _e()]),
    ]
    for b in cases:
        exp = analyze_board(b)
        got = analyze(harness_bin, b)
        assert_match(got, exp)
        assert got["status"] == STATUS_INVALID_INPUT
        assert validate(harness_bin, b, got) == VAL_VALID
        assert validate(harness_bin, b, analyze_board(board(2, 2, [_s(), _f(), _f(), _e()]))) == VAL_INVALID_INPUT


def test_invalid_keys_doors_portals_crumbles(harness_bin: Path) -> None:
    """Duplicate or malformed keys, malformed doors, unpaired portals, and excessive crumble tiles return canonical invalid input."""
    cases = [
        board(2, 2, [_s(), _k("a"), _k("a"), _e()]),
        board(2, 2, [_s(), _k("z"), _f(), _e()]),
        board(2, 2, [_s(), _d("Z"), _f(), _e()]),
        board(2, 2, [_s(), _p("a"), _f(), _e()]),  # unpaired portal
        board(
            2,
            8,
            [_s()]
            + [_c()] * 13
            + [_e()]
            + [_f()] * (16 - 15),
        ),
    ]
    # fix last board to be 2x8 = 16 tiles with 13 crumbles
    cases[-1] = board(2, 8, [_s()] + [_c()] * 13 + [_e(), _f()])
    for b in cases:
        exp = analyze_board(b)
        got = analyze(harness_bin, b)
        assert_match(got, exp)
        assert got["status"] == STATUS_INVALID_INPUT


def test_eight_by_eight_boundary_full_analysis(harness_bin: Path) -> None:
    """An eight-by-eight boundary board with keys, doors, portals, crumbles, route convergence, and a count above 64 bits matches an independently derived complete analysis."""
    # 8x8 open lattice from corner to corner has C(14,7)=3432 shortest routes (combinatorial
    # derivation). Overlay keys/doors/portals/crumbles and a split/rejoin wall notch so every
    # mechanic appears while the independent complete-state model still derives the count as a
    # decimal string (bigint-capable; values may exceed 64-bit registers on other boards).
    cells: list[dict] = [_f() for _ in range(64)]

    def put(r: int, c: int, t: dict) -> None:
        cells[r * 8 + c] = t

    put(0, 0, _s())
    put(7, 7, _e())
    # Soft features that preserve many converging lattice routes:
    put(0, 2, _k("a"))
    put(2, 0, _k("b"))
    put(7, 5, _d("a"))
    put(5, 7, _d("b"))
    put(3, 5, _p("a"))
    put(5, 3, _p("a"))
    put(1, 4, _p("b"))
    put(4, 1, _p("b"))
    put(2, 2, _c())
    put(2, 3, _c())
    put(3, 2, _c())
    put(5, 5, _c())
    put(6, 6, _c())
    put(4, 6, _c())
    # Notch walls creating local split/rejoin without sealing the lattice:
    put(3, 3, _w())
    put(3, 4, _w())

    b = board(8, 8, cells)
    exp = analyze_board(b)
    assert exp["status"] == STATUS_SOLVED
    got = analyze(harness_bin, b)
    assert_match(got, exp)
    assert re.fullmatch(r"[1-9][0-9]*", got["shortest_count"])
    count = int(got["shortest_count"])
    assert count == int(exp["shortest_count"])
    assert got["shortest_count"] == str(count)
    # Decimal string protocol must round-trip beyond fixed-width integers.
    assert str(count + (1 << 64)) != str(count)
    assert validate(harness_bin, b, got) == VAL_VALID
    assert got["decision_points"] is not None
    assert got["mandatory_landings"] is not None
