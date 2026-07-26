"""Independent bounded state-transition model for Opaline cartographer."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

FLOOR, WALL, START, EXIT, KEY, DOOR, CRUMBLE, PORTAL = range(8)
MOVE_UP, MOVE_RIGHT, MOVE_DOWN, MOVE_LEFT = range(4)
MOVE_DELTAS = ((-1, 0), (0, 1), (1, 0), (0, -1))
ALL_MOVES = (MOVE_UP, MOVE_RIGHT, MOVE_DOWN, MOVE_LEFT)

STATUS_SOLVED = 0
STATUS_UNSOLVABLE = 1
STATUS_INVALID_INPUT = 2
STATUS_NOT_IMPLEMENTED = 3

VAL_VALID = 0
VAL_INVALID_INPUT = 1
VAL_INVALID_ANALYSIS = 2


@dataclass(frozen=True)
class State:
    pos: int
    keys: int
    crumb: int


def _empty_analysis(status: int, distance: int) -> dict[str, Any]:
    return {
        "status": status,
        "distance": distance,
        "shortest_count": "0",
        "canonical_moves": [],
        "trace": [],
        "mandatory_landings": [],
        "decision_points": [],
    }


def validate_board(board: dict[str, Any]) -> bool:
    rows = board["rows"]
    cols = board["cols"]
    tiles = board["tiles"]
    if not (2 <= rows <= 8 and 2 <= cols <= 8):
        return False
    if len(tiles) != rows * cols:
        return False
    starts = exits = crumbles = 0
    keys: dict[str, int] = defaultdict(int)
    portals: dict[str, int] = defaultdict(int)
    for tile in tiles:
        kind = tile["kind"]
        tag = tile.get("tag", "")
        if kind in (FLOOR, WALL, START, EXIT, CRUMBLE):
            if tag != "":
                return False
        elif kind in (KEY, DOOR, PORTAL):
            if len(tag) != 1 or not ("a" <= tag <= "d"):
                return False
        else:
            return False
        if kind == START:
            starts += 1
        elif kind == EXIT:
            exits += 1
        elif kind == CRUMBLE:
            crumbles += 1
        elif kind == KEY:
            keys[tag] += 1
        elif kind == PORTAL:
            portals[tag] += 1
    if starts != 1 or exits != 1 or crumbles > 12:
        return False
    if any(n > 1 for n in keys.values()):
        return False
    return all(n == 2 for n in portals.values())


class BoardIndex:
    def __init__(self, board: dict[str, Any]):
        self.rows = board["rows"]
        self.cols = board["cols"]
        self.tiles = board["tiles"]
        n = self.rows * self.cols
        self.portal_partner = [-1] * n
        self.crumble_bit = [-1] * n
        self.crumble_pos: list[int] = []
        self.start = 0
        self.exit = 0
        portals: dict[str, list[int]] = defaultdict(list)
        bit = 0
        for i, t in enumerate(self.tiles):
            kind = t["kind"]
            if kind == START:
                self.start = i
            elif kind == EXIT:
                self.exit = i
            elif kind == CRUMBLE:
                self.crumble_bit[i] = bit
                self.crumble_pos.append(i)
                bit += 1
            elif kind == PORTAL:
                portals[t["tag"]].append(i)
        for pair in portals.values():
            self.portal_partner[pair[0]] = pair[1]
            self.portal_partner[pair[1]] = pair[0]

    def coord(self, i: int) -> tuple[int, int]:
        return divmod(i, self.cols)

    def at(self, r: int, c: int) -> int:
        return r * self.cols + c

    def in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self.rows and 0 <= c < self.cols

    def is_collapsed(self, s: State, cell: int) -> bool:
        b = self.crumble_bit[cell]
        return b >= 0 and (s.crumb & (1 << b)) != 0

    def has_key(self, s: State, tag: str) -> bool:
        return (s.keys & (1 << (ord(tag) - ord("a")))) != 0

    def enterable(self, s: State, cell: int) -> bool:
        if self.is_collapsed(s, cell):
            return False
        t = self.tiles[cell]
        kind = t["kind"]
        if kind == WALL:
            return False
        if kind == DOOR:
            return self.has_key(s, t["tag"])
        return True

    def try_move(self, s: State, m: int) -> State | None:
        r, c = self.coord(s.pos)
        dr, dc = MOVE_DELTAS[m]
        nr, nc = r + dr, c + dc
        if not self.in_bounds(nr, nc):
            return None
        nxt = self.at(nr, nc)
        if not self.enterable(s, nxt):
            return None
        dest = nxt
        if self.portal_partner[nxt] >= 0:
            dest = self.portal_partner[nxt]
            if not self.enterable(s, dest):
                return None
        keys = s.keys
        crumb = s.crumb
        b = self.crumble_bit[s.pos]
        if b >= 0:
            crumb |= 1 << b
        t = self.tiles[dest]
        if t["kind"] == KEY:
            keys |= 1 << (ord(t["tag"]) - ord("a"))
        return State(dest, keys, crumb)

    def is_exit(self, s: State) -> bool:
        return self.tiles[s.pos]["kind"] == EXIT


def _keys_list(mask: int) -> list[str]:
    return [chr(ord("a") + i) for i in range(4) if mask & (1 << i)]


def _collapsed_list(idx: BoardIndex, mask: int) -> list[dict[str, int]]:
    out = []
    for b, cell in enumerate(idx.crumble_pos):
        if mask & (1 << b):
            r, c = idx.coord(cell)
            out.append({"row": r, "col": c})
    out.sort(key=lambda x: (x["row"], x["col"]))
    return out


def analyze_board(board: dict[str, Any]) -> dict[str, Any]:
    if not validate_board(board):
        return _empty_analysis(STATUS_INVALID_INPUT, 0)
    idx = BoardIndex(board)
    start = State(idx.start, 0, 0)

    dist_from: dict[State, int] = {start: 0}
    reachable = {start}
    q: deque[State] = deque([start])
    while q:
        s = q.popleft()
        if idx.is_exit(s):
            continue
        d = dist_from[s]
        for m in ALL_MOVES:
            ns = idx.try_move(s, m)
            if ns is None or ns in dist_from:
                continue
            dist_from[ns] = d + 1
            reachable.add(ns)
            q.append(ns)

    pred: dict[State, list[State]] = defaultdict(list)
    exits: list[State] = []
    for s in reachable:
        if idx.is_exit(s):
            exits.append(s)
            continue
        for m in ALL_MOVES:
            ns = idx.try_move(s, m)
            if ns is not None and ns in reachable:
                pred[ns].append(s)

    dist_to: dict[State, int] = {}
    q = deque()
    for e in exits:
        dist_to[e] = 0
        q.append(e)
    while q:
        s = q.popleft()
        d = dist_to[s]
        for p in pred[s]:
            if p not in dist_to:
                dist_to[p] = d + 1
                q.append(p)

    if start not in dist_to:
        return _empty_analysis(STATUS_UNSOLVABLE, -1)
    distance = dist_to[start]

    on_shortest = {
        s
        for s, d0 in dist_from.items()
        if s in dist_to and d0 + dist_to[s] == distance
    }

    ways: dict[State, int] = {start: 1}
    by_dist: list[list[State]] = [[] for _ in range(distance + 1)]
    for s in on_shortest:
        d = dist_from[s]
        if 0 <= d <= distance:
            by_dist[d].append(s)
    for d in range(distance):
        for s in by_dist[d]:
            w = ways.get(s)
            if w is None or idx.is_exit(s):
                continue
            for m in ALL_MOVES:
                ns = idx.try_move(s, m)
                if ns is None or ns not in on_shortest:
                    continue
                if dist_from[ns] != d + 1:
                    continue
                if dist_to[ns] + d + 1 != distance:
                    continue
                ways[ns] = ways.get(ns, 0) + w

    total = 0
    for s, w in ways.items():
        if idx.is_exit(s) and dist_from[s] == distance:
            total += w

    # Canonical + trace
    canonical: list[int] = []
    trace: list[dict[str, Any]] = []
    s = start
    for step in range(1, distance + 1):
        remaining = distance - step + 1
        chosen = None
        ns = None
        for m in ALL_MOVES:
            cand = idx.try_move(s, m)
            if cand is None:
                continue
            if dist_to.get(cand) == remaining - 1:
                chosen = m
                ns = cand
                break
        assert chosen is not None and ns is not None
        fr = idx.coord(s.pos)
        to = idx.coord(ns.pos)
        canonical.append(chosen)
        trace.append(
            {
                "index": step,
                "move": chosen,
                "from": {"row": fr[0], "col": fr[1]},
                "to": {"row": to[0], "col": to[1]},
                "keys": _keys_list(ns.keys),
                "collapsed": _collapsed_list(idx, ns.crumb),
            }
        )
        s = ns
        if idx.is_exit(s):
            break

    landings: list[dict[str, Any]] = []
    for step in range(1, distance + 1):
        shared = None
        unanimous = True
        for st in on_shortest:
            if dist_from[st] != step:
                continue
            if dist_to[st] + step != distance:
                continue
            c = idx.coord(st.pos)
            if shared is None:
                shared = c
            elif shared != c:
                unanimous = False
                break
        if unanimous and shared is not None:
            landings.append({"step": step, "at": {"row": shared[0], "col": shared[1]}})

    decisions: list[dict[str, Any]] = []
    s = start
    for i, cm in enumerate(canonical):
        step = i + 1
        remaining = distance - i
        alts: list[int] = []
        for m in ALL_MOVES:
            ns = idx.try_move(s, m)
            if ns is None:
                continue
            if dist_to.get(ns) == remaining - 1:
                alts.append(m)
        if len(alts) >= 2:
            r, c = idx.coord(s.pos)
            decisions.append({"step": step, "at": {"row": r, "col": c}, "alternatives": alts})
        ns = idx.try_move(s, cm)
        assert ns is not None
        s = ns

    return {
        "status": STATUS_SOLVED,
        "distance": distance,
        "shortest_count": str(total),
        "canonical_moves": canonical,
        "trace": trace,
        "mandatory_landings": landings,
        "decision_points": decisions,
    }


def analyses_equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return a == b


def validate_analysis(board: dict[str, Any], candidate: dict[str, Any]) -> int:
    expected = analyze_board(board)
    if expected["status"] == STATUS_INVALID_INPUT:
        if analyses_equal(expected, candidate):
            return VAL_VALID
        return VAL_INVALID_INPUT
    if analyses_equal(expected, candidate):
        return VAL_VALID
    return VAL_INVALID_ANALYSIS


def tile(kind: int, tag: str = "") -> dict[str, Any]:
    return {"kind": kind, "tag": tag}


def board(rows: int, cols: int, cells: list[dict[str, Any]]) -> dict[str, Any]:
    return {"rows": rows, "cols": cols, "tiles": cells}
