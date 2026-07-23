import json
import os
import random
import shutil
import subprocess
import tempfile

import pytest

APP_DIR = "/app"
DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]


@pytest.fixture(scope="session")
def judge_bin():
    """Compile the Fortran judge from a copy of /app so /app is never written to."""
    tmp = tempfile.mkdtemp(prefix="hexverdict_build_")
    src = os.path.join(tmp, "src_tree")
    shutil.copytree(APP_DIR, src, symlinks=True, ignore=shutil.ignore_patterns(".git"))
    binp = os.path.join(tmp, "hexverdict")
    proc = subprocess.run(
        ["make", "--no-print-directory", "BIN=" + binp],
        cwd=src,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"build failed:\n{proc.stdout}\n{proc.stderr}"
    assert os.path.isfile(binp), f"build produced no binary:\n{proc.stdout}\n{proc.stderr}"
    return binp


# ---- independent reference judge ----
def _on(q, r, n):
    return max(abs(q), abs(r), abs(-q - r)) <= n - 1


def _all(n):
    return [(q, r) for q in range(-(n - 1), n) for r in range(-(n - 1), n) if _on(q, r, n)]


def _corners(n):
    m = n - 1
    return {(m, 0), (m, -m), (0, m), (0, -m), (-m, 0), (-m, m)}


def _sides(q, r, n):
    m = n - 1
    s = -q - r
    out = set()
    for coord, hi, lo in ((q, 0, 1), (r, 2, 3), (s, 4, 5)):
        if coord == m:
            out.add(hi)
        elif coord == -m:
            out.add(lo)
    return out


def ref_judge(n, cells, player):
    own = {c for c, p in cells.items() if p == player}
    if not own:
        return {"win": False, "type": None}
    cor = _corners(n)
    seen = set()
    comps = []
    for st in own:
        if st in seen:
            continue
        stack = [st]
        seen.add(st)
        comp = []
        while stack:
            c = stack.pop()
            comp.append(c)
            for dq, dr in DIRS:
                nb = (c[0] + dq, c[1] + dr)
                if nb in own and nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        comps.append(comp)

    def has_ring(comp):
        cs = set(comp)
        allc = set(_all(n))
        non = allc - cs
        out = set()
        stack = [c for c in non if _sides(c[0], c[1], n)]
        for c in stack:
            out.add(c)
        while stack:
            c = stack.pop()
            for dq, dr in DIRS:
                nb = (c[0] + dq, c[1] + dr)
                if nb in non and nb not in out:
                    out.add(nb)
                    stack.append(nb)
        return len(non - out) > 0

    found = set()
    for comp in comps:
        if sum(1 for c in comp if c in cor) >= 2:
            found.add("bridge")
        sd = set()
        for c in comp:
            if c not in cor:
                sd |= _sides(c[0], c[1], n)
        if len(sd) >= 3:
            found.add("fork")
        if has_ring(comp):
            found.add("ring")
    for t in ("bridge", "fork", "ring"):
        if t in found:
            return {"win": True, "type": t}
    return {"win": False, "type": None}


def run_bin(binp, inst):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        cells = {f"{q},{r}": v for (q, r), v in inst["cells"].items()}
        json.dump({"size": inst["size"], "player": inst["player"], "cells": cells}, fh)
        path = fh.name
    try:
        proc = subprocess.run([binp, path], capture_output=True, text=True)
        assert proc.returncode == 0, f"binary error: {proc.stderr}"
        return json.loads(proc.stdout)
    finally:
        os.unlink(path)


def check(binp, inst):
    exp = ref_judge(inst["size"], inst["cells"], inst["player"])
    got = run_bin(binp, inst)
    assert got.get("win") == exp["win"] and got.get("type") == exp["type"], (
        f"mismatch on {inst}: expected {exp}, got {got}")


# ---- hand fixtures ----
def test_ring_around_empty(judge_bin):
    """A six-stone loop around an empty central cell is a ring."""
    check(judge_bin, {"size": 4, "player": "A", "cells": {
        (1, 0): "A", (0, 1): "A", (-1, 1): "A", (-1, 0): "A", (0, -1): "A", (1, -1): "A"}})


def test_ring_around_enemy(judge_bin):
    """A loop that encloses an opponent stone still counts as a ring."""
    check(judge_bin, {"size": 4, "player": "A", "cells": {
        (1, 0): "A", (0, 1): "A", (-1, 1): "A", (-1, 0): "A", (0, -1): "A", (1, -1): "A", (0, 0): "B"}})


def test_broken_ring_is_no_win(judge_bin):
    """Five of the six loop stones leave the centre reachable from outside, so it is not a ring."""
    check(judge_bin, {"size": 4, "player": "A", "cells": {
        (1, 0): "A", (0, 1): "A", (-1, 1): "A", (-1, 0): "A", (0, -1): "A"}})


def test_bridge_two_corners(judge_bin):
    """A group linking two corners wins by a bridge."""
    check(judge_bin, {"size": 4, "player": "A", "cells": {
        (3, 0): "A", (3, -1): "A", (3, -2): "A", (3, -3): "A"}})


def test_fork_three_sides(judge_bin):
    """A group reaching three different sides wins by a fork."""
    check(judge_bin, {"size": 4, "player": "A", "cells": {
        (0, 0): "A", (1, 0): "A", (2, 0): "A", (3, -1): "A", (0, 1): "A", (0, 2): "A",
        (-1, 3): "A", (-1, 0): "A", (-2, 0): "A", (-2, -1): "A"}})


def test_two_sides_is_not_fork(judge_bin):
    """A group touching only two sides is not a fork."""
    check(judge_bin, {"size": 4, "player": "A", "cells": {
        (3, -1): "A", (2, 0): "A", (1, 0): "A", (0, 0): "A", (0, 1): "A", (0, 2): "A", (-1, 3): "A"}})


def test_corner_not_counted_as_side(judge_bin):
    """Corner cells must not contribute a side, so a corner plus one side is not a fork."""
    # a single corner plus a border cell on a second side: only 1 side (corner excluded) -> no fork
    check(judge_bin, {"size": 4, "player": "A", "cells": {(3, 0): "A", (2, 1): "A", (1, 2): "A", (0, 3): "A"}})


def test_empty_board_no_win(judge_bin):
    """An empty board is not a win for anyone."""
    check(judge_bin, {"size": 5, "player": "A", "cells": {}})


# ---- randomized differential ----
def _random_instance(rng):
    n = rng.choice([4, 5, 6, 6, 7])
    board = _all(n)
    inst = {"size": n, "player": rng.choice(["A", "B"]), "cells": {}}
    mode = rng.random()
    if mode < 0.55:
        # dense random fill: stresses ring flood-fill on boards with many
        # near-enclosed regions, thin walls, and interior enemy/empty cells.
        pa = rng.uniform(0.35, 0.55)
        pb = rng.uniform(0.05, 0.20)
        for c in board:
            v = rng.random()
            if v < pa:
                inst["cells"][c] = "A"
            elif v < pa + pb:
                inst["cells"][c] = "B"
    elif mode < 0.75:
        # ring-biased: draw a small loop then perturb
        cx = rng.choice(board)
        loop = [(cx[0] + dq, cx[1] + dr) for dq, dr in DIRS]
        for c in loop:
            if _on(c[0], c[1], n) and rng.random() < 0.85:
                inst["cells"][c] = inst["player"]
        for _ in range(rng.randint(0, 6)):
            c = rng.choice(board)
            inst["cells"][c] = rng.choice(["A", "B"])
    else:
        # edge/corner-biased: place along borders
        border = [c for c in board if _sides(c[0], c[1], n)]
        for _ in range(rng.randint(3, 12)):
            c = rng.choice(border)
            inst["cells"][c] = inst["player"] if rng.random() < 0.8 else rng.choice(["A", "B"])
        for _ in range(rng.randint(0, 8)):
            c = rng.choice(board)
            inst["cells"][c] = rng.choice(["A", "B"])
    return inst


CASES = []
_rng = random.Random(20260713)
for _ in range(600):
    CASES.append(_random_instance(_rng))


@pytest.mark.parametrize("inst", CASES)
def test_differential(judge_bin, inst):
    """Generated positions must match the independent reference judge on verdict and structure."""
    check(judge_bin, inst)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-rA"]))
