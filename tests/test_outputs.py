"""Verifier for Emberline Hex Tactics simultaneous-turn resolution."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import pytest

APP = Path("/app/emberline")
SRC = APP / "src" / "main" / "java"
HARNESS_SRC = Path("/tests/harness/ResolverHarness.java")
WORK = Path("/tmp/emberline-verifier")
LIB_CLASSES = WORK / "lib-classes"
HARNESS_CLASSES = WORK / "harness-classes"
HARNESS_MAIN = "ResolverHarness"


@dataclass(frozen=True)
class Event:
    type: str
    unit_id: str
    related: str | None
    at: tuple[int, int] | None
    amount: int


@dataclass(frozen=True)
class UnitState:
    id: str
    team: str
    q: int
    r: int
    health: int
    initiative: int
    range: int
    power: int


@dataclass
class ResolveResult:
    status: str
    amber: int
    cobalt: int
    score_to_win: int
    units: list[UnitState]
    terrain: list[tuple[int, int, str]]
    events: list[Event]
    inputs_untouched: bool
    immutable: tuple[bool, bool, bool]
    raw: str


def _run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


@pytest.fixture(scope="session")
def compiled_harness() -> Path:
    if WORK.exists():
        shutil.rmtree(WORK)
    LIB_CLASSES.mkdir(parents=True)
    HARNESS_CLASSES.mkdir(parents=True)

    sources = sorted(SRC.rglob("*.java"))
    assert sources, f"no Java sources under {SRC}"
    _run(["javac", "--release", "21", "-d", str(LIB_CLASSES), *map(str, sources)])
    _run(
        [
            "javac",
            "--release",
            "21",
            "-cp",
            str(LIB_CLASSES),
            "-d",
            str(HARNESS_CLASSES),
            str(HARNESS_SRC),
        ]
    )
    return HARNESS_CLASSES


def _protocol(
    terrain: list[tuple[int, int, str]],
    units: list[tuple],
    scores: tuple[int, int, int],
    orders: list[tuple],
) -> str:
    lines = ["BOARD"]
    for q, r, kind in terrain:
        lines.append(f"T {q} {r} {kind}")
    for unit in units:
        uid, team, q, r, health, initiative, rng, power = unit
        lines.append(f"U {uid} {team} {q} {r} {health} {initiative} {rng} {power}")
    lines.append(f"S {scores[0]} {scores[1]} {scores[2]}")
    lines.append("END")
    lines.append("ORDERS")
    for order in orders:
        if order[1] == "HOLD" and len(order) == 2:
            lines.append(f"O {order[0]} HOLD")
        elif order[1] == "HOLD" and len(order) == 4:
            lines.append(f"O {order[0]} HOLD {order[2]} {order[3]}")
        else:
            lines.append(f"O {order[0]} {order[1]} {order[2]} {order[3]}")
    lines.append("END")
    lines.append("RESOLVE")
    return "\n".join(lines) + "\n"


def resolve(
    compiled_harness: Path,
    terrain: list[tuple[int, int, str]],
    units: list[tuple],
    scores: tuple[int, int, int],
    orders: list[tuple],
) -> ResolveResult:
    payload = _protocol(terrain, units, scores, orders)
    cp = f"{LIB_CLASSES}{os.pathsep}{compiled_harness}"
    proc = subprocess.run(
        ["java", "-cp", cp, HARNESS_MAIN],
        input=payload,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, f"harness failed\n{proc.stdout}\n{proc.stderr}"
    raw = proc.stdout
    assert raw.startswith("OK\n"), f"expected OK resolution, got:\n{raw}"

    status = ""
    amber = cobalt = score_to_win = 0
    units_out: list[UnitState] = []
    terrain_out: list[tuple[int, int, str]] = []
    events: list[Event] = []
    inputs_untouched = False
    immutable = (False, False, False)

    for line in raw.splitlines():
        if line.startswith("STATUS "):
            status = line.split()[1]
        elif line.startswith("SCORES "):
            _, a, c, w = line.split()
            amber, cobalt, score_to_win = int(a), int(c), int(w)
        elif line.startswith("INPUTS_UNTOUCHED "):
            inputs_untouched = line.split()[1] == "true"
        elif line.startswith("IMMUTABLE "):
            parts = line.split()
            immutable = (parts[1] == "true", parts[2] == "true", parts[3] == "true")
        elif line.startswith("UNIT "):
            _, uid, team, q, r, health, initiative, rng, power = line.split()
            units_out.append(
                UnitState(uid, team, int(q), int(r), int(health), int(initiative), int(rng), int(power))
            )
        elif line.startswith("TERRAIN "):
            _, q, r, kind = line.split()
            terrain_out.append((int(q), int(r), kind))
        elif line.startswith("EVENT "):
            parts = line.split()
            # EVENT TYPE unit related q r amount  OR related=- and at=- -
            etype = parts[1]
            uid = parts[2]
            related = None if parts[3] == "-" else parts[3]
            if parts[4] == "-":
                at = None
                amount = int(parts[6])
            else:
                at = (int(parts[4]), int(parts[5]))
                amount = int(parts[6])
            events.append(Event(etype, uid, related, at, amount))

    return ResolveResult(
        status=status,
        amber=amber,
        cobalt=cobalt,
        score_to_win=score_to_win,
        units=units_out,
        terrain=terrain_out,
        events=events,
        inputs_untouched=inputs_untouched,
        immutable=immutable,
        raw=raw,
    )


def resolve_error(
    compiled_harness: Path,
    terrain: list[tuple[int, int, str]],
    units: list[tuple],
    scores: tuple[int, int, int],
    orders: list[tuple],
) -> str:
    payload = _protocol(terrain, units, scores, orders)
    cp = f"{LIB_CLASSES}{os.pathsep}{compiled_harness}"
    proc = subprocess.run(
        ["java", "-cp", cp, HARNESS_MAIN],
        input=payload,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, f"harness failed\n{proc.stdout}\n{proc.stderr}"
    assert proc.stdout.startswith("ERROR IllegalArgumentException"), proc.stdout
    return proc.stdout


def rectangle(w: int, h: int, fill: str = "PLAIN") -> list[tuple[int, int, str]]:
    return [(q, r, fill) for q in range(w) for r in range(h)]


def unit_pos(result: ResolveResult, uid: str) -> tuple[int, int]:
    for unit in result.units:
        if unit.id == uid:
            return unit.q, unit.r
    raise AssertionError(f"unit {uid} missing")


def unit_health(result: ResolveResult, uid: str) -> int:
    for unit in result.units:
        if unit.id == uid:
            return unit.health
    raise AssertionError(f"unit {uid} missing")


def events_of(result: ResolveResult, etype: str) -> list[Event]:
    return [e for e in result.events if e.type == etype]


# ---------------------------------------------------------------------------
# Independent verifier-side simulator (not a copy of the Java oracle source)
# ---------------------------------------------------------------------------


def _axial_distance(a: tuple[int, int], b: tuple[int, int]) -> int:
    dq = a[0] - b[0]
    dr = a[1] - b[1]
    return (abs(dq) + abs(dr) + abs(dq + dr)) // 2


def simulate(
    terrain: dict[tuple[int, int], str],
    units: list[tuple],
    scores: tuple[int, int, int],
    orders: list[tuple],
) -> tuple[str, list[Event], dict[str, tuple[int, int, int]]]:
    """Return status, events, and surviving unit map id->(q,r,health)."""
    by_id = {
        u[0]: {
            "team": u[1],
            "pos": (u[2], u[3]),
            "health": u[4],
            "initiative": u[5],
            "range": u[6],
            "power": u[7],
        }
        for u in units
    }
    order_map = {}
    for order in orders:
        if order[1] == "HOLD":
            order_map[order[0]] = ("HOLD", None)
        else:
            order_map[order[0]] = (order[1], (order[2], order[3]))

    occupancy = {info["pos"]: uid for uid, info in by_id.items()}
    contenders: dict[tuple[int, int], list[str]] = {}
    for uid, (otype, target) in order_map.items():
        if otype == "MOVE":
            contenders.setdefault(target, []).append(uid)

    retained: dict[str, tuple[int, int]] = {}
    rejected: set[str] = set()
    for dest, ids in contenders.items():
        ids = sorted(ids, key=lambda i: (-by_id[i]["initiative"], i))
        retained[ids[0]] = dest
        rejected.update(ids[1:])

    success: dict[str, bool] = {}
    visiting: set[str] = set()

    def determine(mover: str) -> bool:
        if mover in success:
            return success[mover]
        if mover in visiting:
            return True
        visiting.add(mover)
        dest = retained[mover]
        occ = occupancy.get(dest)
        if occ is None:
            ok = True
        elif occ not in retained:
            ok = False
        elif occ == mover:
            ok = True
        else:
            ok = determine(occ)
        visiting.remove(mover)
        success[mover] = ok
        return ok

    for mover in list(retained):
        determine(mover)

    final_pos = {uid: info["pos"] for uid, info in by_id.items()}
    move_events: list[Event] = []
    for uid in sorted(rejected):
        move_events.append(Event("MOVE_BLOCKED", uid, None, order_map[uid][1], 0))
    for uid in sorted(retained):
        dest = retained[uid]
        if success[uid]:
            final_pos[uid] = dest
            move_events.append(Event("MOVE", uid, None, dest, 0))
        else:
            move_events.append(Event("MOVE_BLOCKED", uid, None, dest, 0))
    move_events.sort(key=lambda e: e.unit_id)

    occ_after = {pos: uid for uid, pos in final_pos.items()}
    damage: dict[str, int] = {}
    attack_events: list[Event] = []
    for uid in sorted(by_id):
        otype, target = order_map[uid]
        if otype != "ATTACK":
            continue
        defender = occ_after.get(target)
        if defender is None or by_id[defender]["team"] == by_id[uid]["team"]:
            attack_events.append(Event("ATTACK_MISS", uid, None, target, 0))
        else:
            power = by_id[uid]["power"]
            attack_events.append(Event("ATTACK_HIT", uid, defender, target, power))
            damage[defender] = damage.get(defender, 0) + power
    attack_events.sort(key=lambda e: e.unit_id)

    for uid, pos in final_pos.items():
        if terrain.get(pos) == "HAZARD":
            damage[uid] = damage.get(uid, 0) + 1

    damage_events: list[Event] = []
    defeat_events: list[Event] = []
    survivors: dict[str, tuple[int, int, int]] = {}
    for uid in sorted(by_id):
        taken = damage.get(uid, 0)
        health = by_id[uid]["health"] - taken
        if taken > 0:
            damage_events.append(Event("DAMAGE", uid, None, final_pos[uid], taken))
        if health <= 0:
            defeat_events.append(Event("DEFEATED", uid, None, None, 0))
        else:
            survivors[uid] = (final_pos[uid][0], final_pos[uid][1], health)

    amber, cobalt, win = scores
    amber_scores: list[Event] = []
    cobalt_scores: list[Event] = []
    for uid in sorted(survivors):
        q, r, _ = survivors[uid]
        if terrain.get((q, r)) != "BEACON":
            continue
        ev = Event("SCORE", uid, None, (q, r), 1)
        if by_id[uid]["team"] == "AMBER":
            amber += 1
            amber_scores.append(ev)
        else:
            cobalt += 1
            cobalt_scores.append(ev)

    if amber >= win and cobalt >= win:
        status = "DRAW"
    elif amber >= win:
        status = "AMBER_WINS"
    elif cobalt >= win:
        status = "COBALT_WINS"
    else:
        status = "ONGOING"

    events = move_events + attack_events + damage_events + defeat_events + amber_scores + cobalt_scores
    return status, events, survivors


# ---------------------------------------------------------------------------
# Tests (exactly 35)
# ---------------------------------------------------------------------------


def test_01_library_and_harness_compile_offline(compiled_harness: Path):
    """The Java 21 library and verifier harness compile offline from a clean directory."""
    assert (LIB_CLASSES / "dev" / "emberline" / "game" / "TurnResolver.class").exists()
    assert (compiled_harness / "ResolverHarness.class").exists()
    # Recompile from a second clean directory to prove offline reproducibility.
    alt = WORK / "alt-lib"
    if alt.exists():
        shutil.rmtree(alt)
    alt.mkdir(parents=True)
    sources = sorted(SRC.rglob("*.java"))
    _run(["javac", "--release", "21", "-d", str(alt), *map(str, sources)])
    assert (alt / "dev" / "emberline" / "game" / "Board.class").exists()


def test_02_library_only_no_public_main():
    """The public environment remains library-only, with no public main class or installed game executable."""
    mains = []
    for path in SRC.rglob("*.java"):
        text = path.read_text(encoding="utf-8")
        if re.search(r"public\s+static\s+void\s+main\s*\(", text):
            mains.append(str(path))
    assert mains == [], f"public main classes found: {mains}"
    for candidate in (
        APP / "emberline",
        APP / "bin" / "emberline",
        Path("/usr/local/bin/emberline"),
        Path("/usr/bin/emberline"),
    ):
        assert not candidate.exists(), f"unexpected executable {candidate}"


def test_03_hold_only_preserves_state(compiled_harness: Path):
    """A turn containing only holds preserves positions, health, scores, and an empty event list."""
    terrain = rectangle(3, 3)
    units = [
        ("a1", "AMBER", 0, 0, 3, 1, 1, 1),
        ("c1", "COBALT", 2, 2, 4, 2, 1, 1),
    ]
    orders = [("a1", "HOLD"), ("c1", "HOLD")]
    result = resolve(compiled_harness, terrain, units, (1, 2, 5), orders)
    assert result.status == "ONGOING"
    assert result.amber == 1 and result.cobalt == 2
    assert {(u.id, u.q, u.r, u.health) for u in result.units} == {
        ("a1", 0, 0, 3),
        ("c1", 2, 2, 4),
    }
    assert result.events == []


def test_04_single_move_into_empty(compiled_harness: Path):
    """A single mover enters an empty adjacent playable hex."""
    terrain = rectangle(3, 2)
    units = [("scout", "AMBER", 0, 0, 2, 1, 1, 1)]
    orders = [("scout", "MOVE", 1, 0)]
    result = resolve(compiled_harness, terrain, units, (0, 0, 3), orders)
    assert unit_pos(result, "scout") == (1, 0)
    assert result.events == [Event("MOVE", "scout", None, (1, 0), 0)]


def test_05_contention_prefers_higher_initiative(compiled_harness: Path):
    """Competing movers select the contender with greater initiative."""
    terrain = rectangle(3, 2)
    units = [
        ("slow", "AMBER", 0, 0, 2, 1, 1, 1),
        ("fast", "COBALT", 2, 0, 2, 5, 1, 1),
    ]
    orders = [("slow", "MOVE", 1, 0), ("fast", "MOVE", 1, 0)]
    result = resolve(compiled_harness, terrain, units, (0, 0, 3), orders)
    assert unit_pos(result, "fast") == (1, 0)
    assert unit_pos(result, "slow") == (0, 0)
    assert events_of(result, "MOVE") == [Event("MOVE", "fast", None, (1, 0), 0)]


def test_06_equal_initiative_prefers_smallest_id(compiled_harness: Path):
    """Equal-initiative contention selects the bytewise-smallest unit ID."""
    terrain = rectangle(3, 2)
    units = [
        ("zeta", "AMBER", 0, 0, 2, 3, 1, 1),
        ("alpha", "COBALT", 2, 0, 2, 3, 1, 1),
    ]
    orders = [("zeta", "MOVE", 1, 0), ("alpha", "MOVE", 1, 0)]
    result = resolve(compiled_harness, terrain, units, (0, 0, 3), orders)
    assert unit_pos(result, "alpha") == (1, 0)
    assert unit_pos(result, "zeta") == (0, 0)


def test_07_rejected_contender_blocked_event(compiled_harness: Path):
    """A rejected contender remains at its source and emits one blocked event."""
    terrain = rectangle(3, 2)
    units = [
        ("a", "AMBER", 0, 0, 2, 1, 1, 1),
        ("b", "COBALT", 2, 0, 2, 9, 1, 1),
    ]
    orders = [("a", "MOVE", 1, 0), ("b", "MOVE", 1, 0)]
    result = resolve(compiled_harness, terrain, units, (0, 0, 3), orders)
    assert unit_pos(result, "a") == (0, 0)
    blocked = events_of(result, "MOVE_BLOCKED")
    assert blocked == [Event("MOVE_BLOCKED", "a", None, (1, 0), 0)]


def test_08_chain_into_empty_succeeds(compiled_harness: Path):
    """A movement chain ending at an empty hex succeeds in full."""
    terrain = rectangle(4, 1)
    units = [
        ("u1", "AMBER", 0, 0, 2, 1, 1, 1),
        ("u2", "AMBER", 1, 0, 2, 1, 1, 1),
    ]
    orders = [("u1", "MOVE", 1, 0), ("u2", "MOVE", 2, 0)]
    result = resolve(compiled_harness, terrain, units, (0, 0, 3), orders)
    assert unit_pos(result, "u1") == (1, 0)
    assert unit_pos(result, "u2") == (2, 0)
    assert [e.type for e in result.events] == ["MOVE", "MOVE"]


def test_09_two_unit_swap_cycle(compiled_harness: Path):
    """A two-unit swap succeeds as a closed movement cycle."""
    terrain = rectangle(2, 1)
    units = [
        ("left", "AMBER", 0, 0, 2, 1, 1, 1),
        ("right", "COBALT", 1, 0, 2, 1, 1, 1),
    ]
    orders = [("left", "MOVE", 1, 0), ("right", "MOVE", 0, 0)]
    result = resolve(compiled_harness, terrain, units, (0, 0, 3), orders)
    assert unit_pos(result, "left") == (1, 0)
    assert unit_pos(result, "right") == (0, 0)
    assert {e.type for e in result.events} == {"MOVE"}


def test_10_longer_rotation_cycle(compiled_harness: Path):
    """A longer closed rotation succeeds without duplicate occupancy."""
    # Triangle of mutually adjacent hexes: (0,0) -> (1,0) -> (0,1) -> (0,0)
    terrain = [(0, 0, "PLAIN"), (1, 0, "PLAIN"), (0, 1, "PLAIN")]
    units = [
        ("a", "AMBER", 0, 0, 2, 1, 1, 1),
        ("b", "AMBER", 1, 0, 2, 1, 1, 1),
        ("c", "COBALT", 0, 1, 2, 1, 1, 1),
    ]
    orders = [("a", "MOVE", 1, 0), ("b", "MOVE", 0, 1), ("c", "MOVE", 0, 0)]
    result = resolve(compiled_harness, terrain, units, (0, 0, 3), orders)
    assert unit_pos(result, "a") == (1, 0)
    assert unit_pos(result, "b") == (0, 1)
    assert unit_pos(result, "c") == (0, 0)
    positions = {(u.q, u.r) for u in result.units}
    assert len(positions) == 3


def test_11_chain_into_holder_fails(compiled_harness: Path):
    """A chain ending at a holding or attacking occupant fails in full."""
    terrain = rectangle(3, 1)
    units = [
        ("pusher", "AMBER", 0, 0, 2, 1, 1, 1),
        ("anchor", "COBALT", 1, 0, 2, 1, 1, 1),
    ]
    orders = [("pusher", "MOVE", 1, 0), ("anchor", "HOLD")]
    result = resolve(compiled_harness, terrain, units, (0, 0, 3), orders)
    assert unit_pos(result, "pusher") == (0, 0)
    assert unit_pos(result, "anchor") == (1, 0)
    assert events_of(result, "MOVE_BLOCKED") == [
        Event("MOVE_BLOCKED", "pusher", None, (1, 0), 0)
    ]

    orders_atk = [("pusher", "MOVE", 1, 0), ("anchor", "ATTACK", 2, 0)]
    result_atk = resolve(compiled_harness, terrain, units, (0, 0, 3), orders_atk)
    assert unit_pos(result_atk, "pusher") == (0, 0)
    assert any(e.type == "MOVE_BLOCKED" and e.unit_id == "pusher" for e in result_atk.events)


def test_12_failure_propagates_through_predecessors(compiled_harness: Path):
    """Failure of a retained downstream move propagates through every predecessor."""
    terrain = rectangle(4, 1)
    units = [
        ("a", "AMBER", 0, 0, 2, 1, 1, 1),
        ("b", "AMBER", 1, 0, 2, 1, 1, 1),
        ("c", "COBALT", 2, 0, 2, 1, 1, 1),
    ]
    orders = [("a", "MOVE", 1, 0), ("b", "MOVE", 2, 0), ("c", "HOLD")]
    result = resolve(compiled_harness, terrain, units, (0, 0, 3), orders)
    assert unit_pos(result, "a") == (0, 0)
    assert unit_pos(result, "b") == (1, 0)
    assert unit_pos(result, "c") == (2, 0)
    blocked_ids = {e.unit_id for e in events_of(result, "MOVE_BLOCKED")}
    assert blocked_ids == {"a", "b"}


def test_13_independent_move_components(compiled_harness: Path):
    """Independent successful and blocked movement components resolve correctly in one turn."""
    terrain = rectangle(5, 2)
    units = [
        ("ok1", "AMBER", 0, 0, 2, 1, 1, 1),
        ("block", "AMBER", 3, 0, 2, 1, 1, 1),
        ("hold", "COBALT", 4, 0, 2, 1, 1, 1),
        ("ok2", "COBALT", 0, 1, 2, 1, 1, 1),
    ]
    orders = [
        ("ok1", "MOVE", 1, 0),
        ("block", "MOVE", 4, 0),
        ("hold", "HOLD"),
        ("ok2", "MOVE", 1, 1),
    ]
    result = resolve(compiled_harness, terrain, units, (0, 0, 3), orders)
    assert unit_pos(result, "ok1") == (1, 0)
    assert unit_pos(result, "ok2") == (1, 1)
    assert unit_pos(result, "block") == (3, 0)
    assert unit_pos(result, "hold") == (4, 0)


def test_14_attack_hits_stationary_opponent(compiled_harness: Path):
    """An attack hits an opposing unit that remains on the targeted post-move hex."""
    terrain = rectangle(3, 1)
    units = [
        ("atk", "AMBER", 0, 0, 3, 1, 2, 2),
        ("def", "COBALT", 2, 0, 3, 1, 1, 1),
    ]
    orders = [("atk", "ATTACK", 2, 0), ("def", "HOLD")]
    result = resolve(compiled_harness, terrain, units, (0, 0, 5), orders)
    assert events_of(result, "ATTACK_HIT") == [
        Event("ATTACK_HIT", "atk", "def", (2, 0), 2)
    ]
    assert unit_health(result, "def") == 1


def test_15_attack_misses_when_target_moves_away(compiled_harness: Path):
    """An attack misses when its intended target moves away."""
    terrain = rectangle(3, 2)
    units = [
        ("atk", "AMBER", 0, 0, 3, 1, 2, 2),
        ("def", "COBALT", 2, 0, 3, 1, 1, 1),
    ]
    orders = [("atk", "ATTACK", 2, 0), ("def", "MOVE", 2, 1)]
    result = resolve(compiled_harness, terrain, units, (0, 0, 5), orders)
    assert events_of(result, "ATTACK_MISS") == [
        Event("ATTACK_MISS", "atk", None, (2, 0), 0)
    ]
    assert unit_health(result, "def") == 3


def test_16_attack_hits_unit_moving_into_hex(compiled_harness: Path):
    """An attack hits an opponent that moves into the targeted hex."""
    terrain = rectangle(3, 2)
    units = [
        ("atk", "AMBER", 0, 0, 3, 1, 2, 2),
        ("def", "COBALT", 2, 1, 3, 1, 1, 1),
    ]
    orders = [("atk", "ATTACK", 2, 0), ("def", "MOVE", 2, 0)]
    result = resolve(compiled_harness, terrain, units, (0, 0, 5), orders)
    assert events_of(result, "ATTACK_HIT") == [
        Event("ATTACK_HIT", "atk", "def", (2, 0), 2)
    ]


def test_17_lethal_attacker_still_strikes(compiled_harness: Path):
    """A lethally damaged attacker still executes its simultaneous attack."""
    terrain = rectangle(2, 1)
    units = [
        ("a", "AMBER", 0, 0, 1, 1, 1, 3),
        ("c", "COBALT", 1, 0, 1, 1, 1, 3),
    ]
    orders = [("a", "ATTACK", 1, 0), ("c", "ATTACK", 0, 0)]
    result = resolve(compiled_harness, terrain, units, (0, 0, 5), orders)
    hits = events_of(result, "ATTACK_HIT")
    assert len(hits) == 2
    assert {e.unit_id for e in hits} == {"a", "c"}
    assert result.units == []
    assert {e.unit_id for e in events_of(result, "DEFEATED")} == {"a", "c"}


def test_18_combined_damage_from_several_attacks(compiled_harness: Path):
    """Several attacks on one defender produce one combined damage event."""
    terrain = rectangle(3, 2)
    units = [
        ("a1", "AMBER", 0, 0, 3, 1, 2, 2),
        ("a2", "AMBER", 0, 1, 3, 1, 2, 3),
        ("def", "COBALT", 2, 0, 9, 1, 1, 1),
    ]
    orders = [("a1", "ATTACK", 2, 0), ("a2", "ATTACK", 2, 0), ("def", "HOLD")]
    result = resolve(compiled_harness, terrain, units, (0, 0, 5), orders)
    damage = events_of(result, "DAMAGE")
    assert damage == [Event("DAMAGE", "def", None, (2, 0), 5)]
    assert unit_health(result, "def") == 4


def test_19_friendly_and_empty_attacks_miss(compiled_harness: Path):
    """An attack against a friendly or empty target emits the correct miss event and no damage."""
    terrain = rectangle(3, 1)
    units = [
        ("a1", "AMBER", 0, 0, 3, 1, 2, 2),
        ("a2", "AMBER", 1, 0, 3, 1, 1, 1),
    ]
    orders = [("a1", "ATTACK", 1, 0), ("a2", "ATTACK", 2, 0)]
    result = resolve(compiled_harness, terrain, units, (0, 0, 5), orders)
    misses = events_of(result, "ATTACK_MISS")
    assert misses == [
        Event("ATTACK_MISS", "a1", None, (1, 0), 0),
        Event("ATTACK_MISS", "a2", None, (2, 0), 0),
    ]
    assert events_of(result, "DAMAGE") == []
    assert unit_health(result, "a2") == 3


def test_20_attack_exactly_at_range(compiled_harness: Path):
    """An attack exactly at the permitted axial range is valid and resolves correctly."""
    terrain = rectangle(4, 1)
    units = [
        ("bow", "AMBER", 0, 0, 3, 1, 3, 2),
        ("mark", "COBALT", 3, 0, 3, 1, 1, 1),
    ]
    assert _axial_distance((0, 0), (3, 0)) == 3
    orders = [("bow", "ATTACK", 3, 0), ("mark", "HOLD")]
    result = resolve(compiled_harness, terrain, units, (0, 0, 5), orders)
    assert events_of(result, "ATTACK_HIT") == [
        Event("ATTACK_HIT", "bow", "mark", (3, 0), 2)
    ]


def test_21_hazard_damage_exactly_one(compiled_harness: Path):
    """A surviving unit on hazard terrain receives exactly one hazard damage."""
    terrain = [(0, 0, "PLAIN"), (1, 0, "HAZARD"), (2, 0, "PLAIN")]
    units = [("runner", "AMBER", 0, 0, 3, 1, 1, 1)]
    orders = [("runner", "MOVE", 1, 0)]
    result = resolve(compiled_harness, terrain, units, (0, 0, 5), orders)
    assert events_of(result, "DAMAGE") == [
        Event("DAMAGE", "runner", None, (1, 0), 1)
    ]
    assert unit_health(result, "runner") == 2


def test_22_attack_and_hazard_combine(compiled_harness: Path):
    """Attack and hazard damage combine into one damage event before defeat evaluation."""
    terrain = [(0, 0, "PLAIN"), (1, 0, "HAZARD")]
    units = [
        ("atk", "AMBER", 0, 0, 3, 1, 1, 2),
        ("def", "COBALT", 1, 0, 3, 1, 1, 1),
    ]
    orders = [("atk", "ATTACK", 1, 0), ("def", "HOLD")]
    result = resolve(compiled_harness, terrain, units, (0, 0, 5), orders)
    assert events_of(result, "DAMAGE") == [
        Event("DAMAGE", "def", None, (1, 0), 3)
    ]
    assert "def" not in {u.id for u in result.units}
    assert any(e.unit_id == "def" and e.type == "DEFEATED" for e in result.events)


def test_23_defeat_events_canonical(compiled_harness: Path):
    """Units reduced to zero or less health are removed and emit canonically ordered defeat events."""
    terrain = rectangle(4, 1)
    units = [
        ("yy", "AMBER", 0, 0, 2, 1, 3, 5),
        ("zz", "AMBER", 3, 0, 2, 1, 3, 5),
        ("m", "COBALT", 1, 0, 1, 1, 1, 1),
        ("a", "COBALT", 2, 0, 1, 1, 1, 1),
    ]
    orders = [
        ("yy", "ATTACK", 1, 0),
        ("zz", "ATTACK", 2, 0),
        ("m", "HOLD"),
        ("a", "HOLD"),
    ]
    result = resolve(compiled_harness, terrain, units, (0, 0, 5), orders)
    defeats = events_of(result, "DEFEATED")
    assert [e.unit_id for e in defeats] == ["a", "m"]
    assert {u.id for u in result.units} == {"yy", "zz"}


def test_24_multiple_beacons_score(compiled_harness: Path):
    """Surviving units on multiple beacons add one score each for their respective teams."""
    terrain = [
        (0, 0, "BEACON"),
        (1, 0, "PLAIN"),
        (2, 0, "BEACON"),
    ]
    units = [
        ("ember", "AMBER", 0, 0, 2, 1, 1, 1),
        ("tide", "COBALT", 2, 0, 2, 1, 1, 1),
    ]
    orders = [("ember", "HOLD"), ("tide", "HOLD")]
    result = resolve(compiled_harness, terrain, units, (0, 0, 5), orders)
    assert result.amber == 1 and result.cobalt == 1
    scores = events_of(result, "SCORE")
    assert scores == [
        Event("SCORE", "ember", None, (0, 0), 1),
        Event("SCORE", "tide", None, (2, 0), 1),
    ]


def test_25_defeated_unit_does_not_score(compiled_harness: Path):
    """A unit defeated during the turn contributes no beacon score."""
    terrain = [(0, 0, "PLAIN"), (1, 0, "BEACON")]
    units = [
        ("atk", "AMBER", 0, 0, 3, 1, 1, 5),
        ("camp", "COBALT", 1, 0, 2, 1, 1, 1),
    ]
    orders = [("atk", "ATTACK", 1, 0), ("camp", "HOLD")]
    result = resolve(compiled_harness, terrain, units, (0, 0, 5), orders)
    assert "camp" not in {u.id for u in result.units}
    assert events_of(result, "SCORE") == []
    assert result.cobalt == 0


def test_26_single_team_victory(compiled_harness: Path):
    """Reaching the score target produces the correct single-team victory status."""
    terrain = [(0, 0, "BEACON"), (1, 0, "PLAIN")]
    units = [
        ("ember", "AMBER", 0, 0, 2, 1, 1, 1),
        ("tide", "COBALT", 1, 0, 2, 1, 1, 1),
    ]
    orders = [("ember", "HOLD"), ("tide", "HOLD")]
    result = resolve(compiled_harness, terrain, units, (4, 0, 5), orders)
    assert result.status == "AMBER_WINS"
    assert result.amber == 5


def test_27_draw_when_both_reach_target(compiled_harness: Path):
    """Both teams reaching the target in the same turn produces DRAW."""
    terrain = [(0, 0, "BEACON"), (1, 0, "BEACON")]
    units = [
        ("ember", "AMBER", 0, 0, 2, 1, 1, 1),
        ("tide", "COBALT", 1, 0, 2, 1, 1, 1),
    ]
    orders = [("ember", "HOLD"), ("tide", "HOLD")]
    result = resolve(compiled_harness, terrain, units, (4, 4, 5), orders)
    assert result.status == "DRAW"
    assert result.amber == 5 and result.cobalt == 5


def test_28_mixed_turn_canonical_event_order(compiled_harness: Path):
    """A mixed turn returns the exact movement, attack, damage, defeat, and score phase ordering and event fields."""
    terrain = [
        (0, 0, "PLAIN"),
        (1, 0, "PLAIN"),
        (2, 0, "HAZARD"),
        (3, 0, "BEACON"),
        (1, 1, "PLAIN"),
    ]
    units = [
        ("amber1", "AMBER", 0, 0, 3, 2, 2, 2),
        ("amber2", "AMBER", 3, 0, 2, 1, 1, 1),
        ("cobalt1", "COBALT", 2, 0, 2, 1, 1, 1),
        ("cobalt2", "COBALT", 1, 1, 2, 1, 1, 1),
    ]
    orders = [
        ("amber1", "MOVE", 1, 0),
        ("amber2", "HOLD"),
        ("cobalt1", "ATTACK", 3, 0),
        ("cobalt2", "MOVE", 1, 0),  # contends with amber1 for (1,0); amber1 wins init
    ]
    result = resolve(compiled_harness, terrain, units, (0, 0, 5), orders)
    types = [e.type for e in result.events]
    phase = []
    for t in types:
        if t in ("MOVE", "MOVE_BLOCKED"):
            phase.append(0)
        elif t in ("ATTACK_HIT", "ATTACK_MISS"):
            phase.append(1)
        elif t == "DAMAGE":
            phase.append(2)
        elif t == "DEFEATED":
            phase.append(3)
        elif t == "SCORE":
            phase.append(4)
    assert phase == sorted(phase)

    terrain_map = {(q, r): k for q, r, k in terrain}
    status, expected_events, _ = simulate(terrain_map, units, (0, 0, 5), orders)
    assert result.status == status
    assert result.events == expected_events


def test_29_permutation_invariant(compiled_harness: Path):
    """Permuting terrain, unit, and order insertion order leaves the resolution unchanged."""
    terrain = [
        (0, 0, "PLAIN"),
        (1, 0, "BEACON"),
        (2, 0, "HAZARD"),
        (0, 1, "PLAIN"),
        (1, 1, "PLAIN"),
    ]
    units = [
        ("b", "AMBER", 0, 0, 3, 2, 2, 1),
        ("a", "COBALT", 2, 0, 3, 1, 1, 2),
        ("c", "AMBER", 0, 1, 2, 3, 1, 1),
    ]
    orders = [
        ("b", "MOVE", 1, 0),
        ("a", "ATTACK", 1, 0),
        ("c", "MOVE", 1, 1),
    ]
    base = resolve(compiled_harness, terrain, units, (1, 1, 5), orders)

    terrain2 = list(reversed(terrain))
    units2 = list(reversed(units))
    orders2 = list(reversed(orders))
    alt = resolve(compiled_harness, terrain2, units2, (1, 1, 5), orders2)
    assert alt.status == base.status
    assert alt.amber == base.amber and alt.cobalt == base.cobalt
    assert alt.units == base.units
    assert alt.events == base.events
    assert alt.terrain == base.terrain

    # Cross-check with independent simulator
    status, events, _ = simulate({(q, r): k for q, r, k in terrain}, units, (1, 1, 5), orders)
    assert base.status == status
    assert base.events == events


def test_30_deterministic_repeat(compiled_harness: Path):
    """Repeating an identical turn produces byte-for-byte equivalent serialized state and events."""
    terrain = rectangle(3, 2)
    units = [
        ("x", "AMBER", 0, 0, 3, 2, 2, 2),
        ("y", "COBALT", 2, 1, 3, 1, 1, 1),
    ]
    orders = [("x", "MOVE", 1, 0), ("y", "ATTACK", 1, 1)]
    first = resolve(compiled_harness, terrain, units, (0, 0, 4), orders)
    second = resolve(compiled_harness, terrain, units, (0, 0, 4), orders)
    assert first.raw == second.raw


def test_31_concurrent_independent_resolutions(compiled_harness: Path):
    """Concurrent independent resolutions are correct and show no shared-state contamination."""
    cases = []
    for i in range(8):
        terrain = rectangle(3, 2)
        units = [
            (f"a{i}", "AMBER", 0, 0, 3, 1 + i, 1, 1),
            (f"c{i}", "COBALT", 2, 0, 3, 1, 1, 1),
        ]
        orders = [(f"a{i}", "MOVE", 1, 0), (f"c{i}", "HOLD")]
        cases.append((terrain, units, (0, 0, 5), orders, f"a{i}"))

    results: dict[str, ResolveResult] = {}
    lock = threading.Lock()

    def run_case(case):
        terrain, units, scores, orders, mover = case
        result = resolve(compiled_harness, terrain, units, scores, orders)
        with lock:
            results[mover] = result

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(run_case, case) for case in cases]
        for fut in as_completed(futures):
            fut.result()

    for terrain, units, scores, orders, mover in cases:
        result = results[mover]
        assert unit_pos(result, mover) == (1, 0)
        assert result.status == "ONGOING"
        # Ensure no foreign unit ids leaked into this result.
        ids = {u.id for u in result.units}
        assert ids == {units[0][0], units[1][0]}


def test_32_immutability_and_no_input_mutation(compiled_harness: Path):
    """Resolution neither mutates input collections nor exposes mutable aliases through returned records."""
    terrain = rectangle(2, 2)
    units = [("u", "AMBER", 0, 0, 2, 1, 1, 1)]
    orders = [("u", "MOVE", 1, 0)]
    result = resolve(compiled_harness, terrain, units, (0, 0, 3), orders)
    assert result.inputs_untouched is True
    assert result.immutable == (True, True, True)


def test_33_invalid_board_nullish_and_scores(compiled_harness: Path):
    """Null data, invalid terrain maps, bad scores, and an invalid score target throw IllegalArgumentException before effects."""
    terrain = rectangle(2, 1)
    units = [("u", "AMBER", 0, 0, 2, 1, 1, 1)]
    orders = [("u", "HOLD")]

    # scoreToWin <= 0
    resolve_error(compiled_harness, terrain, units, (0, 0, 0), orders)
    # score already at/above target
    resolve_error(compiled_harness, terrain, units, (3, 0, 3), orders)
    # negative score
    resolve_error(compiled_harness, terrain, units, (-1, 0, 3), orders)
    # empty terrain
    resolve_error(compiled_harness, [], units, (0, 0, 3), orders)


def test_34_invalid_units_and_positions(compiled_harness: Path):
    """Duplicate IDs or positions, invalid unit fields, wall occupancy, and off-board positions throw IllegalArgumentException."""
    terrain = [(0, 0, "PLAIN"), (1, 0, "WALL"), (2, 0, "PLAIN")]
    # duplicate ids
    resolve_error(
        compiled_harness,
        terrain,
        [("u", "AMBER", 0, 0, 2, 1, 1, 1), ("u", "COBALT", 2, 0, 2, 1, 1, 1)],
        (0, 0, 3),
        [("u", "HOLD")],
    )
    # duplicate positions
    resolve_error(
        compiled_harness,
        [(0, 0, "PLAIN"), (1, 0, "PLAIN")],
        [("a", "AMBER", 0, 0, 2, 1, 1, 1), ("b", "COBALT", 0, 0, 2, 1, 1, 1)],
        (0, 0, 3),
        [("a", "HOLD"), ("b", "HOLD")],
    )
    # wall occupancy
    resolve_error(
        compiled_harness,
        terrain,
        [("w", "AMBER", 1, 0, 2, 1, 1, 1)],
        (0, 0, 3),
        [("w", "HOLD")],
    )
    # off board
    resolve_error(
        compiled_harness,
        terrain,
        [("o", "AMBER", 9, 9, 2, 1, 1, 1)],
        (0, 0, 3),
        [("o", "HOLD")],
    )
    # non-positive health
    resolve_error(
        compiled_harness,
        terrain,
        [("h", "AMBER", 0, 0, 0, 1, 1, 1)],
        (0, 0, 3),
        [("h", "HOLD")],
    )
    # bad id
    resolve_error(
        compiled_harness,
        terrain,
        [("-bad", "AMBER", 0, 0, 2, 1, 1, 1)],
        (0, 0, 3),
        [("-bad", "HOLD")],
    )


def test_35_invalid_orders(compiled_harness: Path):
    """Missing, duplicate, unknown, malformed, non-adjacent, wall-targeted, off-board, or out-of-range orders throw IllegalArgumentException."""
    terrain = [(0, 0, "PLAIN"), (1, 0, "PLAIN"), (2, 0, "WALL"), (0, 1, "PLAIN")]
    units = [
        ("a", "AMBER", 0, 0, 2, 1, 1, 1),
        ("b", "COBALT", 1, 0, 2, 1, 1, 1),
    ]

    # missing order
    resolve_error(compiled_harness, terrain, units, (0, 0, 3), [("a", "HOLD")])
    # duplicate order
    resolve_error(
        compiled_harness,
        terrain,
        units,
        (0, 0, 3),
        [("a", "HOLD"), ("b", "HOLD"), ("a", "HOLD")],
    )
    # unknown unit
    resolve_error(
        compiled_harness,
        terrain,
        units,
        (0, 0, 3),
        [("a", "HOLD"), ("ghost", "HOLD")],
    )
    # HOLD with non-null target
    resolve_error(
        compiled_harness,
        terrain,
        units,
        (0, 0, 3),
        [("a", "HOLD", 1, 0), ("b", "HOLD")],
    )
    # non-adjacent move
    resolve_error(
        compiled_harness,
        terrain,
        units,
        (0, 0, 3),
        [("a", "MOVE", 1, 1), ("b", "HOLD")],
    )
    # wall-targeted move
    resolve_error(
        compiled_harness,
        terrain,
        units,
        (0, 0, 3),
        [("a", "HOLD"), ("b", "MOVE", 2, 0)],
    )
    # off-board attack
    resolve_error(
        compiled_harness,
        terrain,
        units,
        (0, 0, 3),
        [("a", "ATTACK", 9, 9), ("b", "HOLD")],
    )
    # out of range attack
    terrain2 = rectangle(5, 1)
    units2 = [("a", "AMBER", 0, 0, 2, 1, 1, 1), ("b", "COBALT", 4, 0, 2, 1, 1, 1)]
    resolve_error(
        compiled_harness,
        terrain2,
        units2,
        (0, 0, 3),
        [("a", "ATTACK", 4, 0), ("b", "HOLD")],
    )
