"""End-to-end verification for the Compose Dungeon game server.

test.sh compiles /app offline into /tmp/dungeond and the tests-owned bbolt
dump helper into /tmp/dbdump. These tests then play the game over HTTP
against the shipped dungeon plus verifier-owned compose maps, checking the
gameplay rules, the reachability computation, per-player item state, the
win condition, crash durability, and the on-disk bbolt layout.
"""

import json
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest
import requests

TESTS_DIR = Path(__file__).resolve().parent
SERVER_BIN = Path("/tmp/dungeond")
DBDUMP_BIN = Path("/tmp/dbdump")
SHIPPED_WORLD = "/app/world/docker-compose.yml"
FORMS_WORLD = str(TESTS_DIR / "worlds" / "forms.yml")
MAZE_WORLD = str(TESTS_DIR / "worlds" / "maze.yml")
BRANCH_WORLD = str(TESTS_DIR / "worlds" / "branch.yml")

_ports = iter(range(18310, 18600))


class Dungeon:
    """Runs one dungeond process against a given world and database path."""

    def __init__(self, compose, db_path, port=None):
        self.port = port if port is not None else next(_ports)
        self.compose = compose
        self.db_path = str(db_path)
        self.base = f"http://127.0.0.1:{self.port}"
        self.proc = None

    def start(self):
        assert SERVER_BIN.exists(), "server binary missing: go build of /app failed"
        self.proc = subprocess.Popen(
            [
                str(SERVER_BIN),
                "-addr",
                f"127.0.0.1:{self.port}",
                "-db",
                self.db_path,
                "-compose",
                self.compose,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 15
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise AssertionError("server process exited during startup")
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.25):
                    return self
            except OSError:
                time.sleep(0.1)
        raise AssertionError("server did not start listening within 15s")

    def kill(self):
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
        if self.proc:
            self.proc.wait(timeout=10)

    def terminate(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        if self.proc:
            self.proc.wait(timeout=10)

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.kill()

    def get(self, path):
        return requests.get(self.base + path, timeout=10)

    def post(self, path, body=None, raw=None):
        if raw is not None:
            return requests.post(self.base + path, data=raw, timeout=10)
        return requests.post(self.base + path, json=body, timeout=10)


def rooms_by_name(world_json):
    return {r["name"]: r for r in world_json["rooms"]}


def dbdump(path):
    """Dump a bbolt database file as {bucket: {key: value}} via the
    tests-owned helper binary."""
    out = subprocess.run(
        [str(DBDUMP_BIN), str(path)], capture_output=True, text=True, check=True
    )
    return json.loads(out.stdout)


SHIPPED_ROOMS = {
    "cellar": {
        "exits": ["courtyard", "crypt"],
        "lock": None,
        "dark": True,
        "goal": False,
        "items": ["key.silver"],
        "reachable": True,
    },
    "chapel": {
        "exits": ["courtyard", "vault"],
        "lock": "iron",
        "dark": False,
        "goal": False,
        "items": ["gem.amber", "key.gold"],
        "reachable": True,
    },
    "courtyard": {
        "exits": ["cellar", "chapel", "gatehouse"],
        "lock": None,
        "dark": False,
        "goal": False,
        "items": ["key.iron"],
        "reachable": True,
    },
    "crypt": {
        "exits": ["cellar"],
        "lock": "silver",
        "dark": True,
        "goal": False,
        "items": ["gem.onyx", "torch"],
        "reachable": True,
    },
    "gatehouse": {
        "exits": ["courtyard"],
        "lock": None,
        "dark": False,
        "goal": False,
        "items": ["torch"],
        "reachable": True,
    },
    "observatory": {
        "exits": ["oubliette"],
        "lock": None,
        "dark": False,
        "goal": False,
        "items": [],
        "reachable": False,
    },
    "oubliette": {
        "exits": ["observatory"],
        "lock": "bone",
        "dark": False,
        "goal": False,
        "items": ["key.bone"],
        "reachable": False,
    },
    "vault": {
        "exits": ["chapel"],
        "lock": "gold",
        "dark": False,
        "goal": True,
        "items": ["crown"],
        "reachable": True,
    },
}

FORMS_ROOMS = {
    "archive": {
        "exits": ["bluevault", "lobby"],
        "lock": "red",
        "dark": False,
        "goal": False,
        "items": ["map"],
        "reachable": True,
    },
    "basement": {
        "exits": ["lobby"],
        "lock": None,
        "dark": True,
        "goal": False,
        "items": ["key.blue", "torch"],
        "reachable": True,
    },
    "bluevault": {
        "exits": ["archive"],
        "lock": "blue",
        "dark": False,
        "goal": True,
        "items": ["gem.sapphire"],
        "reachable": False,
    },
    "lobby": {
        "exits": ["archive", "basement"],
        "lock": None,
        "dark": False,
        "goal": False,
        "items": ["coin", "key.red"],
        "reachable": True,
    },
}

MAZE_ROOMS = {
    "hub": {
        "exits": {"east", "north", "south"},
        "lock": None,
        "dark": False,
        "goal": False,
        "items": {"key.green", "torch"},
    },
    "north": {
        "exits": {"attic", "hub"},
        "lock": None,
        "dark": False,
        "goal": False,
        "items": {"key.white"},
    },
    "east": {
        "exits": {"attic", "hub"},
        "lock": "green",
        "dark": False,
        "goal": False,
        "items": {"gem.emerald"},
    },
    "south": {
        "exits": {"blackroom", "hub"},
        "lock": None,
        "dark": True,
        "goal": False,
        "items": {"gem.moss", "key.black"},
    },
    "attic": {
        "exits": {"east", "north"},
        "lock": "white",
        "dark": False,
        "goal": True,
        "items": {"lens"},
    },
    "blackroom": {
        "exits": {"south"},
        "lock": "black",
        "dark": True,
        "goal": False,
        "items": {"gem.void"},
    },
    "isolated": {
        "exits": set(),
        "lock": None,
        "dark": False,
        "goal": False,
        "items": {"gem.lost"},
    },
}

BRANCH_ROOMS = {
    "start": {
        "exits": {"alcove", "beacon", "cavern"},
        "lock": None,
        "dark": False,
        "goal": False,
        "items": set(),
    },
    "alcove": {
        "exits": {"start"},
        "lock": None,
        "dark": False,
        "goal": False,
        "items": {"coin"},
    },
    "beacon": {
        "exits": {"start", "vault"},
        "lock": None,
        "dark": False,
        "goal": False,
        "items": {"key.gold"},
    },
    "cavern": {
        "exits": {"start", "vault"},
        "lock": None,
        "dark": False,
        "goal": False,
        "items": {"key.gold"},
    },
    "vault": {
        "exits": {"beacon", "cavern"},
        "lock": "gold",
        "dark": False,
        "goal": True,
        "items": {"crown"},
    },
}


def test_server_builds_offline():
    """The Go module at /app must compile offline into a server binary
    (test.sh runs `go build` with GOPROXY=off before pytest starts)."""
    assert SERVER_BIN.exists(), "go build of /app did not produce a binary"
    assert DBDUMP_BIN.exists(), "verifier dbdump helper failed to build"


def test_world_contract_shipped(tmp_path):
    """GET /world on the shipped compose map returns rooms sorted by name,
    with sorted exits and items, lock color or null, and dark/goal flags
    exactly matching the service labels and depends_on edges."""
    with Dungeon(SHIPPED_WORLD, tmp_path / "w.db") as d:
        resp = d.get("/world")
        assert resp.status_code == 200
        body = resp.json()
        assert body["entry"] == "gatehouse"
        assert body["par"] == 3, f"par should be 3, got {body['par']}"
        assert [r["name"] for r in body["rooms"]] == sorted(SHIPPED_ROOMS)
        got = rooms_by_name(body)
        for name, want in SHIPPED_ROOMS.items():
            expected = {"name": name, **want}
            assert got[name] == expected, f"room {name}: {got[name]}"


def test_world_reachability_shipped(tmp_path):
    """Reachability on the shipped map: the key-behind-lock chain
    (iron -> gold, torch -> silver) is fully reachable, while the
    disconnected observatory/oubliette island is not."""
    with Dungeon(SHIPPED_WORLD, tmp_path / "w.db") as d:
        got = rooms_by_name(d.get("/world").json())
        for name, want in SHIPPED_ROOMS.items():
            assert got[name]["reachable"] is want["reachable"], name


def test_session_creation_and_ids(tmp_path):
    """POST /sessions returns 201 with zero-padded sequential ids starting
    at s000001 and a fresh player state at the entry room."""
    with Dungeon(SHIPPED_WORLD, tmp_path / "s.db") as d:
        r1 = d.post("/sessions")
        assert r1.status_code == 201
        assert r1.json() == {
            "id": "s000001",
            "room": "gatehouse",
            "inventory": [],
            "moves": 0,
            "won": False,
        }
        r2 = d.post("/sessions")
        assert r2.status_code == 201
        assert r2.json()["id"] == "s000002"
        g = d.get("/sessions/s000001")
        assert g.status_code == 200
        assert g.json() == r1.json()


def test_unknown_session_is_404(tmp_path):
    """Requests naming a session that was never created return 404 with
    error code unknown-session, even when the body is malformed."""
    with Dungeon(SHIPPED_WORLD, tmp_path / "u.db") as d:
        r = d.get("/sessions/s000042")
        assert r.status_code == 404
        assert r.json() == {"error": "unknown-session"}
        r = d.post("/sessions/s000042/move", raw=b"not json at all")
        assert r.status_code == 404
        assert r.json() == {"error": "unknown-session"}


def test_move_rule_precedence(tmp_path):
    """Moves are validated as room existence, then a connecting door, then
    the lock: an existing-but-distant locked room reports no-door, a fake
    room reports unknown-room, an adjacent locked room reports locked, and
    failed moves never increment the moves counter."""
    with Dungeon(SHIPPED_WORLD, tmp_path / "m.db") as d:
        d.post("/sessions")
        r = d.post("/sessions/s000001/move", {"to": "vault"})
        assert (r.status_code, r.json()) == (409, {"error": "no-door"})
        r = d.post("/sessions/s000001/move", {"to": "throneroom"})
        assert (r.status_code, r.json()) == (409, {"error": "unknown-room"})
        r = d.post("/sessions/s000001/move", {"to": "gatehouse"})
        assert (r.status_code, r.json()) == (409, {"error": "no-door"})
        r = d.post("/sessions/s000001/move", {"to": "courtyard"})
        assert r.status_code == 200
        r = d.post("/sessions/s000001/move", {"to": "chapel"})
        assert (r.status_code, r.json()) == (409, {"error": "locked"})
        state = d.get("/sessions/s000001").json()
        assert state["room"] == "courtyard"
        assert state["moves"] == 1


def test_bad_request_bodies(tmp_path):
    """Malformed bodies (non-JSON, missing, non-string or empty fields)
    return 400 bad-request and leave the session untouched."""
    with Dungeon(SHIPPED_WORLD, tmp_path / "b.db") as d:
        d.post("/sessions")
        for raw in (b"not json", b"{}", b'{"to": 5}', b'{"to": ""}'):
            r = d.post("/sessions/s000001/move", raw=raw)
            assert (r.status_code, r.json()) == (400, {"error": "bad-request"}), raw
        for raw in (b"[1,2]", b'{"item": null}', b'{"item": ""}'):
            r = d.post("/sessions/s000001/take", raw=raw)
            assert (r.status_code, r.json()) == (400, {"error": "bad-request"}), raw
        assert d.get("/sessions/s000001").json() == {
            "id": "s000001",
            "room": "gatehouse",
            "inventory": [],
            "moves": 0,
            "won": False,
        }


def test_move_rejects_extra_fields_and_trailing_data(tmp_path):
    """A move with an unexpected key, second JSON value, or trailing garbage
    returns 400 without changing the session or creating a journal entry."""
    db = tmp_path / "move_strict.db"
    with Dungeon(SHIPPED_WORLD, db) as d:
        fresh = d.post("/sessions").json()
        for raw in (
            b'{"to": "courtyard", "extra": true}',
            b'{"to":"courtyard"}{"extra":true}',
            b'{"to":"courtyard"} garbage',
        ):
            r = d.post("/sessions/s000001/move", raw=raw)
            assert (r.status_code, r.json()) == (
                400,
                {"error": "bad-request"},
            ), raw
        assert d.get("/sessions/s000001").json() == fresh
        d.terminate()
    dump = dbdump(db)
    assert json.loads(dump["sessions"]["s000001"]) == fresh
    assert dump.get("journal", {}) == {}


def test_take_rejects_extra_fields_and_trailing_data(tmp_path):
    """A take with an unexpected key, second JSON value, or trailing garbage
    returns 400 without changing the session or creating a journal entry."""
    db = tmp_path / "take_strict.db"
    with Dungeon(SHIPPED_WORLD, db) as d:
        fresh = d.post("/sessions").json()
        for raw in (
            b'{"item": "torch", "extra": true}',
            b'{"item":"torch"}{"extra":true}',
            b'{"item":"torch"} garbage',
        ):
            r = d.post("/sessions/s000001/take", raw=raw)
            assert (r.status_code, r.json()) == (
                400,
                {"error": "bad-request"},
            ), raw
        assert d.get("/sessions/s000001").json() == fresh
        d.terminate()
    dump = dbdump(db)
    assert json.loads(dump["sessions"]["s000001"]) == fresh
    assert dump.get("journal", {}) == {}


def test_keys_unlock_and_are_reusable(tmp_path):
    """Carrying key.<color> lets a player enter a room locked with that
    color, and the key is not consumed: the player can leave and re-enter
    while moves counts each successful move."""
    with Dungeon(SHIPPED_WORLD, tmp_path / "k.db") as d:
        d.post("/sessions")
        assert d.post("/sessions/s000001/move", {"to": "courtyard"}).status_code == 200
        assert d.post("/sessions/s000001/take", {"item": "key.iron"}).status_code == 200
        assert d.post("/sessions/s000001/move", {"to": "chapel"}).status_code == 200
        assert d.post("/sessions/s000001/move", {"to": "courtyard"}).status_code == 200
        r = d.post("/sessions/s000001/move", {"to": "chapel"})
        assert r.status_code == 200
        assert r.json() == {
            "id": "s000001",
            "room": "chapel",
            "inventory": ["key.iron"],
            "moves": 4,
            "won": False,
        }


def test_dark_rooms_need_a_torch(tmp_path):
    """Dark rooms can be entered freely but refuse every take with 409
    dark until the player carries a torch; the dark check also fires for
    items that are not even in the room."""
    with Dungeon(SHIPPED_WORLD, tmp_path / "d.db") as d:
        d.post("/sessions")
        d.post("/sessions/s000001/move", {"to": "courtyard"})
        r = d.post("/sessions/s000001/move", {"to": "cellar"})
        assert r.status_code == 200
        r = d.post("/sessions/s000001/take", {"item": "key.silver"})
        assert (r.status_code, r.json()) == (409, {"error": "dark"})
        r = d.post("/sessions/s000001/take", {"item": "phantom"})
        assert (r.status_code, r.json()) == (409, {"error": "dark"})
        for to in ("courtyard", "gatehouse"):
            assert d.post("/sessions/s000001/move", {"to": to}).status_code == 200
        assert d.post("/sessions/s000001/take", {"item": "torch"}).status_code == 200
        for to in ("courtyard", "cellar"):
            assert d.post("/sessions/s000001/move", {"to": to}).status_code == 200
        r = d.post("/sessions/s000001/take", {"item": "key.silver"})
        assert r.status_code == 200
        assert d.post("/sessions/s000001/move", {"to": "crypt"}).status_code == 200
        r = d.post("/sessions/s000001/take", {"item": "gem.onyx"})
        assert r.status_code == 200
        assert r.json() == {
            "id": "s000001",
            "room": "crypt",
            "inventory": ["gem.onyx", "key.silver", "torch"],
            "moves": 7,
            "won": False,
        }


def test_take_is_idempotent(tmp_path):
    """Taking an item you already carry is a 200 no-op that changes
    nothing, and taking something not in the room is 409 no-item."""
    with Dungeon(SHIPPED_WORLD, tmp_path / "t.db") as d:
        d.post("/sessions")
        first = d.post("/sessions/s000001/take", {"item": "torch"})
        assert first.status_code == 200
        again = d.post("/sessions/s000001/take", {"item": "torch"})
        assert again.status_code == 200
        assert again.json() == first.json()
        for item in ("crown", "key.iron"):
            r = d.post("/sessions/s000001/take", {"item": item})
            assert (r.status_code, r.json()) == (409, {"error": "no-item"}), item


def test_sessions_have_private_items(tmp_path):
    """Each player plays on their own copy of the dungeon's items: one
    session taking the torch does not remove it for another session, and
    GET /world keeps reporting the compose-defined items."""
    with Dungeon(SHIPPED_WORLD, tmp_path / "p.db") as d:
        d.post("/sessions")
        assert d.post("/sessions/s000001/take", {"item": "torch"}).status_code == 200
        d.post("/sessions")
        r = d.post("/sessions/s000002/take", {"item": "torch"})
        assert r.status_code == 200
        assert r.json()["inventory"] == ["torch"]
        world = rooms_by_name(d.get("/world").json())
        assert world["gatehouse"]["items"] == ["torch"]


def test_winning_at_the_goal_room(tmp_path):
    """Moving into the goal room flips won to true and winning is sticky:
    the flag stays true after the player wanders back out."""
    with Dungeon(SHIPPED_WORLD, tmp_path / "win.db") as d:
        d.post("/sessions")
        assert d.post("/sessions/s000001/move", {"to": "courtyard"}).status_code == 200
        assert d.post("/sessions/s000001/take", {"item": "key.iron"}).status_code == 200
        assert d.post("/sessions/s000001/move", {"to": "chapel"}).status_code == 200
        assert d.post("/sessions/s000001/take", {"item": "key.gold"}).status_code == 200
        r = d.post("/sessions/s000001/move", {"to": "vault"})
        assert r.status_code == 200
        assert r.json() == {
            "id": "s000001",
            "room": "vault",
            "inventory": ["key.gold", "key.iron"],
            "moves": 3,
            "won": True,
        }
        r = d.post("/sessions/s000001/move", {"to": "chapel"})
        assert r.status_code == 200
        assert r.json()["won"] is True
        assert r.json()["room"] == "chapel"


def test_state_survives_sigkill(tmp_path):
    """Every acknowledged state change is committed to bbolt before the
    response: after SIGKILL and a restart on the same database, all
    sessions are intact and the id counter keeps counting."""
    db = tmp_path / "crash.db"
    d = Dungeon(SHIPPED_WORLD, db).start()
    try:
        d.post("/sessions")
        assert d.post("/sessions/s000001/take", {"item": "torch"}).status_code == 200
        assert d.post("/sessions/s000001/move", {"to": "courtyard"}).status_code == 200
        assert d.post("/sessions/s000001/take", {"item": "key.iron"}).status_code == 200
        d.post("/sessions")
        state1 = d.get("/sessions/s000001").json()
        state2 = d.get("/sessions/s000002").json()
        assert state1 == {
            "id": "s000001",
            "room": "courtyard",
            "inventory": ["key.iron", "torch"],
            "moves": 1,
            "won": False,
        }
    finally:
        d.kill()
    with Dungeon(SHIPPED_WORLD, db, port=d.port) as d2:
        assert d2.get("/sessions/s000001").json() == state1
        assert d2.get("/sessions/s000002").json() == state2
        r = d2.post("/sessions")
        assert r.status_code == 201
        assert r.json()["id"] == "s000003"


def test_bbolt_database_layout(tmp_path):
    """The bbolt file contains a sessions bucket mapping each id to the
    exact JSON object the API returns for it, and a meta bucket whose
    last_id key holds the last issued counter value as a decimal string."""
    db = tmp_path / "layout.db"
    with Dungeon(SHIPPED_WORLD, db) as d:
        d.post("/sessions")
        assert d.post("/sessions/s000001/take", {"item": "torch"}).status_code == 200
        assert d.post("/sessions/s000001/move", {"to": "courtyard"}).status_code == 200
        d.post("/sessions")
        api = {sid: d.get(f"/sessions/{sid}").json() for sid in ("s000001", "s000002")}
        d.terminate()
    dump = dbdump(db)
    assert "sessions" in dump and "meta" in dump, sorted(dump)
    assert set(dump["sessions"]) == {"s000001", "s000002"}
    for sid, raw in dump["sessions"].items():
        assert json.loads(raw) == api[sid], sid
    assert dump["meta"]["last_id"] == "2"


def test_agent_left_a_winning_save():
    """Playing the shipped dungeon is part of the job: the default save at
    /app/data/dungeon.db must already contain a finished run, meaning a
    session with won true whose inventory holds both keys needed to reach
    the vault and at least the three moves the shortest route takes."""
    save = Path("/app/data/dungeon.db")
    assert save.exists(), "no save file at /app/data/dungeon.db"
    dump = dbdump(save)
    sessions = [json.loads(v) for v in dump.get("sessions", {}).values()]
    winners = [s for s in sessions if s.get("won") is True]
    assert winners, "no winning run found in /app/data/dungeon.db"
    assert any(
        {"key.gold", "key.iron"} <= set(s.get("inventory", []))
        and s.get("moves", 0) >= 3
        for s in winners
    ), f"winning runs look implausible: {winners}"


def test_world_contract_alternate_syntax(tmp_path):
    """Compose maps using list-form labels, long-form depends_on maps,
    and untrimmed item lists produce the same world contract."""
    with Dungeon(FORMS_WORLD, tmp_path / "f.db") as d:
        body = d.get("/world").json()
        assert (
            body["par"] is None
        ), f"unwinnable map should have par null, got {body['par']}"
        assert body["entry"] == "lobby"
        assert [r["name"] for r in body["rooms"]] == sorted(FORMS_ROOMS)
        got = rooms_by_name(body)
        for name, want in FORMS_ROOMS.items():
            assert got[name] == {"name": name, **want}, name


def test_torch_trapped_in_dark_room(tmp_path):
    """When the only torch sits inside a dark room it can never be picked
    up, so reachability must not count that room's items: the bluevault
    goal stays unreachable (the dungeon is unwinnable) and takes in the
    basement keep failing with dark."""
    with Dungeon(FORMS_WORLD, tmp_path / "trap.db") as d:
        got = rooms_by_name(d.get("/world").json())
        assert got["bluevault"]["reachable"] is False
        assert got["basement"]["reachable"] is True
        d.post("/sessions")
        assert d.post("/sessions/s000001/move", {"to": "basement"}).status_code == 200
        for item in ("torch", "key.blue"):
            r = d.post("/sessions/s000001/take", {"item": item})
            assert (r.status_code, r.json()) == (409, {"error": "dark"}), item


def test_par_counts_only_moves(tmp_path):
    """par is the fewest moves to stand in the goal room, and looting is
    free: on the maze the two-move route through north to fetch key.white
    beats any longer detour, so par is 2 even though loot is picked up on
    the way."""
    with Dungeon(MAZE_WORLD, tmp_path / "par.db") as d:
        body = d.get("/world").json()
        assert body["par"] == 2, f"maze par should be 2, got {body['par']}"


def test_world_route_shipped(tmp_path):
    """route is one concrete shortest way to win: the rooms a fresh player moves
    into, in order, to first reach the goal, with length equal to par. On the
    shipped map the only three-move win is courtyard, chapel, vault."""
    with Dungeon(SHIPPED_WORLD, tmp_path / "route.db") as d:
        body = d.get("/world").json()
        assert body["route"] == ["courtyard", "chapel", "vault"], body["route"]
        assert len(body["route"]) == body["par"]


def test_world_route_lexicographic_tiebreak(tmp_path):
    """When several shortest routes exist, route is the lexicographically
    smallest one, and it never wanders into a dead end whose name happens to
    sort first: on the branch map beacon and cavern are both two-move wins that
    each hold the key the goal needs, and alcove is a dead end sorting before
    both, so the route is beacon then vault."""
    with Dungeon(BRANCH_WORLD, tmp_path / "branch.db") as d:
        body = d.get("/world").json()
        assert body["par"] == 2, f"branch par should be 2, got {body['par']}"
        assert body["route"] == ["beacon", "vault"], body["route"]


def test_world_route_null_when_unwinnable(tmp_path):
    """route is null exactly when par is null: an unwinnable map has no winning
    move sequence to report."""
    with Dungeon(FORMS_WORLD, tmp_path / "route_null.db") as d:
        body = d.get("/world").json()
        assert body["par"] is None
        assert body["route"] is None


_REPLAY_SEED = 0x243F6A8885A308D3

@pytest.mark.parametrize(
    "world,expected",
    [
        pytest.param(
            SHIPPED_WORLD,
            {
                "seed": _REPLAY_SEED,
                "steps": ["courtyard", "chapel", "vault"],
                "won": True,
            },
            id="shipped",
        ),
        pytest.param(
            MAZE_WORLD,
            {
                "seed": _REPLAY_SEED,
                "steps": ["north", "hub", "north", "attic"],
                "won": True,
            },
            id="maze",
        ),
        pytest.param(
            BRANCH_WORLD,
            {
                "seed": _REPLAY_SEED,
                "steps": ["beacon", "vault"],
                "won": True,
            },
            id="branch",
        ),
    ],
)
def test_world_replay_matches_sealed_expectations(world, expected, tmp_path):
    """GET /replay is a fixed SplitMix64 bot playthrough: seeded to the contract
    constant, choosing each move by unbiased rejection sampling over the sorted
    enterable doors and looting greedily. Its complete response must match
    sealed expected data for each verifier-owned map."""
    with Dungeon(world, tmp_path / "replay.db") as d:
        response = d.get("/replay")
        assert response.status_code == 200
        assert response.json() == expected


def test_undo_rewinds_moves_and_pickups(tmp_path):
    """Undo restores the exact previous state of a run: the last pickup
    disappears from the inventory, the last move gives back both the room
    and the moves count, and undoing on a fresh run is 409
    nothing-to-undo."""
    with Dungeon(SHIPPED_WORLD, tmp_path / "undo.db") as d:
        fresh = d.post("/sessions").json()
        r = d.post("/sessions/s000001/undo")
        assert (r.status_code, r.json()) == (409, {"error": "nothing-to-undo"})
        assert d.post("/sessions/s000001/take", {"item": "torch"}).status_code == 200
        after_move = d.post("/sessions/s000001/move", {"to": "courtyard"}).json()
        assert after_move["moves"] == 1
        r = d.post("/sessions/s000001/undo")
        assert r.status_code == 200
        assert r.json() == {
            "id": "s000001",
            "room": "gatehouse",
            "inventory": ["torch"],
            "moves": 0,
            "won": False,
        }
        r = d.post("/sessions/s000001/undo")
        assert r.status_code == 200
        assert r.json() == fresh
        r = d.post("/sessions/s000001/undo")
        assert (r.status_code, r.json()) == (409, {"error": "nothing-to-undo"})


def test_undo_ignores_failed_and_no_op_actions(tmp_path):
    """Only changes that actually changed something are undoable: rejected
    moves and repeat takes of an item already carried leave the undo
    history alone."""
    with Dungeon(SHIPPED_WORLD, tmp_path / "noop.db") as d:
        d.post("/sessions")
        assert d.post("/sessions/s000001/take", {"item": "torch"}).status_code == 200
        for _ in range(3):
            assert (
                d.post("/sessions/s000001/take", {"item": "torch"}).status_code == 200
            )
        assert d.post("/sessions/s000001/move", {"to": "vault"}).status_code == 409
        assert d.post("/sessions/s000001/take", {"item": "crown"}).status_code == 409
        r = d.post("/sessions/s000001/undo")
        assert r.status_code == 200
        assert r.json()["inventory"] == []
        r = d.post("/sessions/s000001/undo")
        assert (r.status_code, r.json()) == (409, {"error": "nothing-to-undo"})


def test_undo_takes_back_a_win(tmp_path):
    """Winning is sticky against wandering but not against undo: rewinding
    the move that entered the goal room clears won again, and replaying
    that move wins once more."""
    with Dungeon(SHIPPED_WORLD, tmp_path / "unwin.db") as d:
        d.post("/sessions")
        d.post("/sessions/s000001/move", {"to": "courtyard"})
        d.post("/sessions/s000001/take", {"item": "key.iron"})
        d.post("/sessions/s000001/move", {"to": "chapel"})
        d.post("/sessions/s000001/take", {"item": "key.gold"})
        assert d.post("/sessions/s000001/move", {"to": "vault"}).json()["won"] is True
        r = d.post("/sessions/s000001/undo")
        assert r.status_code == 200
        assert r.json() == {
            "id": "s000001",
            "room": "chapel",
            "inventory": ["key.gold", "key.iron"],
            "moves": 2,
            "won": False,
        }
        assert d.post("/sessions/s000001/move", {"to": "vault"}).json()["won"] is True


def test_undo_history_survives_restart(tmp_path):
    """The undo log lives in the save file, so a run rewinds correctly even
    after the server is SIGKILLed and restarted on the same database."""
    db = tmp_path / "undocrash.db"
    d = Dungeon(SHIPPED_WORLD, db).start()
    try:
        d.post("/sessions")
        assert d.post("/sessions/s000001/take", {"item": "torch"}).status_code == 200
        assert d.post("/sessions/s000001/move", {"to": "courtyard"}).status_code == 200
        assert d.post("/sessions/s000001/take", {"item": "key.iron"}).status_code == 200
    finally:
        d.kill()
    with Dungeon(SHIPPED_WORLD, db, port=d.port) as d2:
        r = d2.post("/sessions/s000001/undo")
        assert r.status_code == 200
        assert r.json()["inventory"] == ["torch"]
        r = d2.post("/sessions/s000001/undo")
        assert r.status_code == 200
        assert r.json() == {
            "id": "s000001",
            "room": "gatehouse",
            "inventory": ["torch"],
            "moves": 0,
            "won": False,
        }


def test_journal_bucket_layout(tmp_path):
    """The journal bucket is the append-only undo log: keys are the session
    id, a colon, and a 6-digit sequence starting at 000001, values are the
    run's state before each change, and undo removes the newest entry."""
    db = tmp_path / "journal.db"
    with Dungeon(SHIPPED_WORLD, db) as d:
        d.post("/sessions")
        d.post("/sessions/s000001/take", {"item": "torch"})
        d.post("/sessions/s000001/move", {"to": "courtyard"})
        d.post("/sessions")
        d.post("/sessions/s000002/take", {"item": "torch"})
        d.terminate()
    dump = dbdump(db)
    assert "journal" in dump, sorted(dump)
    assert sorted(dump["journal"]) == [
        "s000001:000001",
        "s000001:000002",
        "s000002:000001",
    ]
    first = json.loads(dump["journal"]["s000001:000001"])
    second = json.loads(dump["journal"]["s000001:000002"])
    assert first == {
        "id": "s000001",
        "room": "gatehouse",
        "inventory": [],
        "moves": 0,
        "won": False,
    }
    assert second == {
        "id": "s000001",
        "room": "gatehouse",
        "inventory": ["torch"],
        "moves": 0,
        "won": False,
    }
    with Dungeon(SHIPPED_WORLD, db) as d:
        assert d.post("/sessions/s000001/undo").status_code == 200
        d.terminate()
    after = dbdump(db)
    assert sorted(after["journal"]) == ["s000001:000001", "s000002:000001"]


def test_concurrent_runs_get_unique_ids(tmp_path):
    """Twenty runs started at the same time must get twenty distinct
    sequential ids with no gaps or duplicates, and the saved state has to
    agree with what the API handed out."""
    with Dungeon(SHIPPED_WORLD, tmp_path / "conc.db") as d:
        results = []
        lock = threading.Lock()

        def start_run():
            resp = d.post("/sessions")
            with lock:
                results.append((resp.status_code, resp.json()))

        threads = [threading.Thread(target=start_run) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert all(status == 201 for status, _ in results), results
        ids = sorted(body["id"] for _, body in results)
        assert ids == [f"s{n:06d}" for n in range(1, 21)], ids
        for _, body in results:
            assert d.get(f"/sessions/{body['id']}").json() == body
        d.terminate()
    dump = dbdump(tmp_path / "conc.db")
    assert sorted(dump["sessions"]) == ids
    assert dump["meta"]["last_id"] == "20"


MAZE_SESSION_TRANSCRIPT = [
    (
        "/sessions",
        None,
        201,
        {
            "id": "s000001",
            "room": "hub",
            "inventory": [],
            "moves": 0,
            "won": False,
        },
    ),
    (
        "/sessions/s000001/move",
        {"to": "east"},
        409,
        {"error": "locked"},
    ),
    (
        "/sessions/s000001/take",
        {"item": "torch"},
        200,
        {
            "id": "s000001",
            "room": "hub",
            "inventory": ["torch"],
            "moves": 0,
            "won": False,
        },
    ),
    (
        "/sessions/s000001/take",
        {"item": "key.green"},
        200,
        {
            "id": "s000001",
            "room": "hub",
            "inventory": ["key.green", "torch"],
            "moves": 0,
            "won": False,
        },
    ),
    (
        "/sessions/s000001/move",
        {"to": "east"},
        200,
        {
            "id": "s000001",
            "room": "east",
            "inventory": ["key.green", "torch"],
            "moves": 1,
            "won": False,
        },
    ),
    (
        "/sessions/s000001/take",
        {"item": "gem.emerald"},
        200,
        {
            "id": "s000001",
            "room": "east",
            "inventory": ["gem.emerald", "key.green", "torch"],
            "moves": 1,
            "won": False,
        },
    ),
    (
        "/sessions/s000001/move",
        {"to": "attic"},
        409,
        {"error": "locked"},
    ),
    (
        "/sessions/s000001/move",
        {"to": "hub"},
        200,
        {
            "id": "s000001",
            "room": "hub",
            "inventory": ["gem.emerald", "key.green", "torch"],
            "moves": 2,
            "won": False,
        },
    ),
    (
        "/sessions/s000001/move",
        {"to": "north"},
        200,
        {
            "id": "s000001",
            "room": "north",
            "inventory": ["gem.emerald", "key.green", "torch"],
            "moves": 3,
            "won": False,
        },
    ),
    (
        "/sessions/s000001/take",
        {"item": "key.white"},
        200,
        {
            "id": "s000001",
            "room": "north",
            "inventory": ["gem.emerald", "key.green", "key.white", "torch"],
            "moves": 3,
            "won": False,
        },
    ),
    (
        "/sessions/s000001/move",
        {"to": "attic"},
        200,
        {
            "id": "s000001",
            "room": "attic",
            "inventory": ["gem.emerald", "key.green", "key.white", "torch"],
            "moves": 4,
            "won": True,
        },
    ),
    (
        "/sessions/s000001/move",
        {"to": "east"},
        200,
        {
            "id": "s000001",
            "room": "east",
            "inventory": ["gem.emerald", "key.green", "key.white", "torch"],
            "moves": 5,
            "won": True,
        },
    ),
    (
        "/sessions/s000001/undo",
        None,
        200,
        {
            "id": "s000001",
            "room": "attic",
            "inventory": ["gem.emerald", "key.green", "key.white", "torch"],
            "moves": 4,
            "won": True,
        },
    ),
    (
        "/sessions/s000001/undo",
        None,
        200,
        {
            "id": "s000001",
            "room": "north",
            "inventory": ["gem.emerald", "key.green", "key.white", "torch"],
            "moves": 3,
            "won": False,
        },
    ),
    (
        "/sessions/s000001/undo",
        None,
        200,
        {
            "id": "s000001",
            "room": "north",
            "inventory": ["gem.emerald", "key.green", "torch"],
            "moves": 3,
            "won": False,
        },
    ),
]


def test_maze_session_matches_sealed_transcript(tmp_path):
    """A fixed verifier-owned maze transcript covers locks, sorted inventory,
    sticky wins, and exact undo snapshots without duplicating server logic."""
    with Dungeon(MAZE_WORLD, tmp_path / "maze.db") as d:
        got = rooms_by_name(d.get("/world").json())
        for name in MAZE_ROOMS:
            assert got[name]["reachable"] is (name != "isolated"), name

        for step, (path, body, status, expected) in enumerate(
            MAZE_SESSION_TRANSCRIPT
        ):
            response = d.post(path, body)
            assert (response.status_code, response.json()) == (
                status,
                expected,
            ), f"sealed transcript step {step}: {path}"
        assert d.get("/sessions/s000001").json() == MAZE_SESSION_TRANSCRIPT[-1][3]
