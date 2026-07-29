"""Behavioral checks for the Redeal solitaire study."""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

OPENINGS_DIR = Path("/app/openings")
OUT_DIR = Path("/app/report")
SRC_DIR = Path("/app/src")
BUILD_DIR = Path("/app/build")
BINARY = BUILD_DIR / "redeal"

OPENINGS_JSON = OUT_DIR / "openings.json"
SIZES_JSON = OUT_DIR / "sizes.json"
ALL_OUTPUTS = (OPENINGS_JSON, SIZES_JSON)

EXPECTED_INPUT_TREE_SHA256 = "2c8b82e54a246caee3158660983a3467482067117435d46cfd674cc0a13d6d73"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def input_tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(root)).replace("\\", "/")
            h.update(rel.encode("utf-8"))
            h.update(b"\0")
            h.update(p.read_bytes())
            h.update(b"\0")
    return h.hexdigest()


def is_canonical_json(path: Path) -> tuple[bool, str]:
    raw = path.read_bytes()
    if not raw.endswith(b"\n"):
        return False, f"{path} missing trailing newline"
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return False, f"{path} not utf-8: {exc}"
    payload = json.loads(decoded)
    canonical = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    if decoded != canonical:
        return False, f"{path} is not canonical 2-space sorted-key JSON"
    return True, ""


# ---------------------------------------------------------------------------
# Independent re-derivation of the game (mirrors /app/docs)
# ---------------------------------------------------------------------------


def canonical(heaps: list[int]) -> list[int]:
    """Heap sizes with non-positive entries dropped, sorted non-increasing."""
    return sorted((h for h in heaps if h > 0), reverse=True)


def redeal(pos: list[int]) -> list[int]:
    """One move: drop one counter per heap, discard emptied heaps, add a new heap
    whose size equals the number of heaps before the move."""
    s = len(pos)
    nxt = [h - 1 for h in pos if h - 1 > 0]
    nxt.append(s)
    nxt.sort(reverse=True)
    return nxt


def partitions(n: int) -> list[list[int]]:
    """Every position with n counters, each as a non-increasing list."""
    out: list[list[int]] = []
    cur: list[int] = []

    def gen(rem: int, mx: int) -> None:
        if rem == 0:
            out.append(cur.copy())
            return
        for first in range(min(rem, mx), 0, -1):
            cur.append(first)
            gen(rem - first, first)
            cur.pop()

    gen(n, n)
    return out


def partition_count(n: int) -> int:
    """Number of positions with n counters, via an independent recurrence."""
    dp = [0] * (n + 1)
    dp[0] = 1
    for part in range(1, n + 1):
        for total in range(part, n + 1):
            dp[total] += dp[total - part]
    return dp[n]


def analyze(n: int) -> dict[str, Any]:
    """Full study of every position with n counters."""
    nodes = partitions(n)
    N = len(nodes)
    idx = {tuple(p): i for i, p in enumerate(nodes)}
    succ = [0] * N
    indeg = [0] * N
    for i, p in enumerate(nodes):
        j = idx[tuple(redeal(p))]
        succ[i] = j
        indeg[j] += 1

    state = [0] * N
    preperiod = [-1] * N
    cycle_id = [-1] * N
    path_pos = [-1] * N
    cycle_members: list[list[int]] = []
    next_cid = 0

    for s0 in range(N):
        if state[s0] != 0:
            continue
        path: list[int] = []
        u = s0
        while state[u] == 0:
            state[u] = 1
            path_pos[u] = len(path)
            path.append(u)
            u = succ[u]
        if state[u] == 1:
            pos = path_pos[u]
            cid = next_cid
            next_cid += 1
            members = []
            for k in range(pos, len(path)):
                w = path[k]
                cycle_id[w] = cid
                preperiod[w] = 0
                state[w] = 2
                members.append(w)
            cycle_members.append(members)
            for k in range(pos - 1, -1, -1):
                w = path[k]
                nx = succ[w]
                preperiod[w] = preperiod[nx] + 1
                cycle_id[w] = cycle_id[nx]
                state[w] = 2
        else:
            for k in range(len(path) - 1, -1, -1):
                w = path[k]
                nx = succ[w]
                preperiod[w] = preperiod[nx] + 1
                cycle_id[w] = cycle_id[nx]
                state[w] = 2
        for w in path:
            path_pos[w] = -1

    cycles: list[list[list[int]]] = []
    for cid in range(next_cid):
        members = cycle_members[cid]
        best = min(members, key=lambda w: nodes[w])
        ordered = []
        c = best
        while True:
            ordered.append(nodes[c])
            c = succ[c]
            if c == best:
                break
        cycles.append(ordered)

    return {
        "nodes": nodes,
        "idx": idx,
        "indeg": indeg,
        "preperiod": preperiod,
        "cycle_id": cycle_id,
        "cycles": cycles,
        "positions": N,
        "longest_settling": max(preperiod) if N else 0,
        "unreachable_positions": sum(1 for i in range(N) if indeg[i] == 0),
    }


def build_reference(openings: list[dict]) -> dict[str, Any]:
    """Compute the two report documents from a list of {id, heaps} openings."""
    norm = [(o["id"], canonical(list(o["heaps"]))) for o in openings]
    norm = [(cid, heaps, sum(heaps)) for cid, heaps in norm]
    sizes = sorted({n for _, _, n in norm})
    analyses = {n: analyze(n) for n in sizes}

    opening_recs = []
    for cid, heaps, n in norm:
        a = analyses[n]
        i = a["idx"][tuple(heaps)]
        c = a["cycle_id"][i]
        opening_recs.append({
            "arrivals": a["indeg"][i],
            "counters": n,
            "endgame": [list(p) for p in a["cycles"][c]],
            "endgame_length": len(a["cycles"][c]),
            "heaps": list(heaps),
            "id": cid,
            "reachable": a["indeg"][i] > 0,
            "redeals_to_endgame": a["preperiod"][i],
        })
    opening_recs.sort(key=lambda r: r["id"])

    size_recs = []
    for n in sizes:
        a = analyses[n]
        ordered_cycles = sorted(a["cycles"], key=lambda c: c[0])
        size_recs.append({
            "endgames": [
                {"cycle": [list(p) for p in c], "length": len(c)}
                for c in ordered_cycles
            ],
            "longest_settling": a["longest_settling"],
            "positions": a["positions"],
            "size": n,
            "unreachable_positions": a["unreachable_positions"],
        })
    size_recs.sort(key=lambda r: r["size"])

    return {"openings": {"openings": opening_recs}, "sizes": {"sizes": size_recs}}


def read_openings(root: Path) -> list[dict]:
    """Read the pinned openings folder into {id, heaps} dicts."""
    out = []
    for p in sorted(root.glob("*.json")):
        j = load_json(p)
        out.append({"id": j["id"], "heaps": list(j["heaps"])})
    return out


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def expected_outputs() -> dict[str, Any]:
    return build_reference(read_openings(OPENINGS_DIR))


@pytest.fixture(scope="session")
def binary_run() -> dict[str, Any]:
    assert BINARY.exists(), f"binary not found at {BINARY}; sources must be built here"
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    start = time.time()
    proc = subprocess.run(
        [str(BINARY), str(OPENINGS_DIR), str(OUT_DIR)],
        capture_output=True, text=True, timeout=300, check=False,
    )
    return {"start": start, "returncode": proc.returncode,
            "stdout": proc.stdout, "stderr": proc.stderr}


def _write_openings(dir_path: Path, openings: list[dict]) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    for i, o in enumerate(openings):
        (dir_path / f"op{i:03d}.json").write_text(json.dumps(o), encoding="utf-8")


def _run_on(tmp_path: Path, openings: list[dict]) -> dict[str, Any]:
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    _write_openings(in_dir, openings)
    out_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [str(BINARY), str(in_dir), str(out_dir)],
        capture_output=True, text=True, timeout=300, check=False,
    )
    assert proc.returncode == 0, f"rc={proc.returncode} stderr={proc.stderr!r}"
    return {
        "openings": load_json(out_dir / "openings.json"),
        "sizes": load_json(out_dir / "sizes.json"),
    }


# ---------------------------------------------------------------------------
# Build / plumbing
# ---------------------------------------------------------------------------


def test_inputs_unchanged() -> None:
    """The openings tree must match the pinned snapshot hash."""
    actual = input_tree_hash(OPENINGS_DIR)
    assert actual == EXPECTED_INPUT_TREE_SHA256, (
        f"openings tree hash {actual} does not match pinned "
        f"{EXPECTED_INPUT_TREE_SHA256}"
    )


def test_binary_built_and_executable() -> None:
    """A real ELF program must be built at /app/build/redeal from C++ sources."""
    assert BINARY.exists(), f"expected compiled program at {BINARY}"
    mode = BINARY.stat().st_mode
    assert mode & stat.S_IXUSR, f"{BINARY} is not executable"
    assert BINARY.stat().st_size > 1024, f"{BINARY} suspiciously small"
    with BINARY.open("rb") as fh:
        assert fh.read(4) == b"\x7fELF", f"{BINARY} is not an ELF executable"
    srcs = list(SRC_DIR.rglob("*.cpp")) + list(SRC_DIR.rglob("*.cc")) + list(SRC_DIR.rglob("*.cxx"))
    assert srcs, "expected C++ sources under /app/src"
    assert sum(p.stat().st_size for p in srcs) > 2048, "C++ sources implausibly small"


def test_binary_newer_than_sources() -> None:
    """The program must be newer than its sources (no shipped prebuilt binary)."""
    srcs = (
        list(SRC_DIR.rglob("*.cpp")) + list(SRC_DIR.rglob("*.cc"))
        + list(SRC_DIR.rglob("*.cxx")) + list(SRC_DIR.rglob("*.hpp"))
        + list(SRC_DIR.rglob("*.h"))
    )
    assert srcs, "no C++ sources found under /app/src"
    assert BINARY.stat().st_mtime >= max(p.stat().st_mtime for p in srcs), (
        "binary older than newest source; looks prebuilt"
    )


def test_binary_runs_cleanly(binary_run: dict[str, Any]) -> None:
    """The program exits 0 and writes exactly the two reports, freshly."""
    assert binary_run["returncode"] == 0, (
        f"redeal exited {binary_run['returncode']}; stderr={binary_run['stderr']!r}"
    )
    for path in ALL_OUTPUTS:
        assert path.exists(), f"missing output: {path}"
        assert path.stat().st_size > 0, f"empty output: {path}"
        assert path.stat().st_mtime + 1.0 >= binary_run["start"], f"stale output: {path}"
        load_json(path)
    extras = {p.name for p in OUT_DIR.iterdir() if p.is_file()} - {p.name for p in ALL_OUTPUTS}
    assert not extras, f"unexpected extra output files: {sorted(extras)}"


@pytest.mark.parametrize("n_args", [0, 1, 3])
def test_wrong_arg_counts(tmp_path: Path, n_args: int) -> None:
    """The program requires exactly two positional arguments."""
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    argv = [str(BINARY)]
    if n_args >= 1:
        argv.append(str(a))
    if n_args >= 2:
        argv.append(str(b))
    if n_args >= 3:
        argv.append("extra")
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=60, check=False)
    assert proc.returncode != 0, f"expected non-zero for {n_args} args"


def test_missing_directories(tmp_path: Path) -> None:
    """A missing openings or output directory is an error."""
    good = tmp_path / "good"
    _write_openings(good, [{"id": "a", "heaps": [3]}])
    out = tmp_path / "out"
    out.mkdir()
    p1 = subprocess.run([str(BINARY), str(tmp_path / "nope"), str(out)],
                        capture_output=True, text=True, timeout=60, check=False)
    assert p1.returncode != 0, "missing openings dir must error"
    p2 = subprocess.run([str(BINARY), str(good), str(tmp_path / "nope_out")],
                        capture_output=True, text=True, timeout=60, check=False)
    assert p2.returncode != 0, "missing output dir must error"


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def test_outputs_canonical_json(binary_run: dict[str, Any]) -> None:
    """Both reports are canonical 2-space sorted-key JSON with a trailing newline."""
    assert binary_run["returncode"] == 0
    for path in ALL_OUTPUTS:
        ok, msg = is_canonical_json(path)
        assert ok, msg


def test_outputs_ascii(binary_run: dict[str, Any]) -> None:
    """Both reports are pure ASCII."""
    assert binary_run["returncode"] == 0
    for path in ALL_OUTPUTS:
        raw = path.read_bytes()
        for i, byte in enumerate(raw):
            assert byte < 0x80, f"{path} byte {i} = 0x{byte:02x} is non-ASCII"


# ---------------------------------------------------------------------------
# Correctness against the independent re-derivation
# ---------------------------------------------------------------------------


def test_openings_match_reference(binary_run: dict[str, Any], expected_outputs: dict[str, Any]) -> None:
    """openings.json equals the independently re-derived report."""
    assert binary_run["returncode"] == 0
    assert load_json(OPENINGS_JSON) == expected_outputs["openings"]


def test_sizes_match_reference(binary_run: dict[str, Any], expected_outputs: dict[str, Any]) -> None:
    """sizes.json equals the independently re-derived report."""
    assert binary_run["returncode"] == 0
    assert load_json(SIZES_JSON) == expected_outputs["sizes"]


# ---------------------------------------------------------------------------
# Structural / semantic properties of the pinned run
# ---------------------------------------------------------------------------


def test_openings_sorted_by_id(binary_run: dict[str, Any]) -> None:
    """Openings are listed in ascending id order."""
    assert binary_run["returncode"] == 0
    ids = [r["id"] for r in load_json(OPENINGS_JSON)["openings"]]
    assert ids == sorted(ids), f"openings not sorted by id: {ids}"


def test_sizes_sorted_ascending(binary_run: dict[str, Any]) -> None:
    """Sizes are listed in ascending size order, one per distinct total."""
    assert binary_run["returncode"] == 0
    sizes = [r["size"] for r in load_json(SIZES_JSON)["sizes"]]
    assert sizes == sorted(sizes)
    assert len(sizes) == len(set(sizes)), "duplicate size records"


def test_size_set_matches_openings(binary_run: dict[str, Any]) -> None:
    """The studied sizes are exactly the distinct counter totals of the openings."""
    assert binary_run["returncode"] == 0
    openings = load_json(OPENINGS_JSON)["openings"]
    sizes = load_json(SIZES_JSON)["sizes"]
    assert {r["size"] for r in sizes} == {r["counters"] for r in openings}


def test_heaps_canonical_and_counters(binary_run: dict[str, Any]) -> None:
    """Each opening's heaps are non-increasing and counters equals their sum."""
    assert binary_run["returncode"] == 0
    for r in load_json(OPENINGS_JSON)["openings"]:
        heaps = r["heaps"]
        assert heaps == sorted(heaps, reverse=True), f"{r['id']} heaps not canonical"
        assert all(h >= 1 for h in heaps), f"{r['id']} has a non-positive heap"
        assert sum(heaps) == r["counters"], f"{r['id']} counters mismatch"


def test_reachable_matches_arrivals(binary_run: dict[str, Any]) -> None:
    """reachable is true exactly when arrivals is positive."""
    assert binary_run["returncode"] == 0
    for r in load_json(OPENINGS_JSON)["openings"]:
        assert r["reachable"] == (r["arrivals"] > 0), f"{r['id']} reachable/arrivals disagree"
        assert r["arrivals"] >= 0


def test_endgame_is_a_canonical_cycle(binary_run: dict[str, Any]) -> None:
    """Each endgame begins at its smallest position, each entry redeals into the
    next, the last redeals back to the first, and the length field agrees."""
    assert binary_run["returncode"] == 0
    for r in load_json(OPENINGS_JSON)["openings"]:
        eg = r["endgame"]
        assert len(eg) == r["endgame_length"] >= 1, f"{r['id']} endgame length mismatch"
        assert eg[0] == min(eg), f"{r['id']} endgame does not start at its smallest position"
        for k in range(len(eg)):
            nxt = eg[(k + 1) % len(eg)]
            assert redeal(eg[k]) == nxt, f"{r['id']} endgame is not closed under redeals"
        for pos in eg:
            assert pos == sorted(pos, reverse=True), f"{r['id']} endgame position not canonical"


def test_settling_reaches_endgame(binary_run: dict[str, Any]) -> None:
    """Applying redeals_to_endgame moves from an opening lands on an endgame position."""
    assert binary_run["returncode"] == 0
    for r in load_json(OPENINGS_JSON)["openings"]:
        pos = list(r["heaps"])
        for _ in range(r["redeals_to_endgame"]):
            pos = redeal(pos)
        assert pos in r["endgame"], f"{r['id']} does not reach its endgame in the stated moves"
        if r["redeals_to_endgame"] > 0:
            assert list(r["heaps"]) not in r["endgame"], (
                f"{r['id']} claims positive settling but starts on the endgame"
            )


def test_positions_equal_partition_count(binary_run: dict[str, Any]) -> None:
    """positions for each size equals the partition count from an independent recurrence."""
    assert binary_run["returncode"] == 0
    for r in load_json(SIZES_JSON)["sizes"]:
        assert r["positions"] == partition_count(r["size"]), f"size {r['size']} positions wrong"


def test_size_endgames_sorted(binary_run: dict[str, Any]) -> None:
    """A size's endgames are listed by smallest position and lengths agree."""
    assert binary_run["returncode"] == 0
    for r in load_json(SIZES_JSON)["sizes"]:
        firsts = [e["cycle"][0] for e in r["endgames"]]
        assert firsts == sorted(firsts), f"size {r['size']} endgames not ordered"
        for e in r["endgames"]:
            assert e["length"] == len(e["cycle"]) >= 1


# ---------------------------------------------------------------------------
# Dataset coverage (both branches of every reported distinction occur)
# ---------------------------------------------------------------------------


def test_program_reports_both_endgame_lengths(binary_run: dict[str, Any]) -> None:
    """The program's report shows both single-position and longer endgames."""
    assert binary_run["returncode"] == 0
    lengths = {r["endgame_length"] for r in load_json(OPENINGS_JSON)["openings"]}
    assert 1 in lengths, "no opening settles onto a single-position endgame"
    assert any(v > 1 for v in lengths), "no opening reaches a multi-position endgame"


def test_program_reports_both_reachability(binary_run: dict[str, Any]) -> None:
    """The program marks some openings reachable and some never-produced."""
    assert binary_run["returncode"] == 0
    flags = {r["reachable"] for r in load_json(OPENINGS_JSON)["openings"]}
    assert flags == {True, False}, f"reachability not both covered: {flags}"


def test_program_reports_both_settling(binary_run: dict[str, Any]) -> None:
    """The program shows an already-settled opening and ones needing redeals."""
    assert binary_run["returncode"] == 0
    settles = {r["redeals_to_endgame"] for r in load_json(OPENINGS_JSON)["openings"]}
    assert 0 in settles, "no opening already on its endgame"
    assert any(v > 0 for v in settles), "no opening needs any redeals"


def test_program_reports_unreachable_positions(binary_run: dict[str, Any]) -> None:
    """The program finds at least one size with never-produced positions."""
    assert binary_run["returncode"] == 0
    assert any(r["unreachable_positions"] > 0 for r in load_json(SIZES_JSON)["sizes"])


# ---------------------------------------------------------------------------
# Hidden datasets (behaviour on openings not in the pinned set)
# ---------------------------------------------------------------------------


def test_hidden_multi_position_endgame(tmp_path: Path) -> None:
    """Four counters as heaps 3 and 1 sit on a three-position endgame."""
    got = _run_on(tmp_path, [{"id": "x", "heaps": [1, 3]}])
    ref = build_reference([{"id": "x", "heaps": [1, 3]}])
    assert got["openings"] == ref["openings"]
    rec = got["openings"]["openings"][0]
    assert rec["endgame"] == [[2, 1, 1], [3, 1], [2, 2]]
    assert rec["endgame_length"] == 3
    assert rec["redeals_to_endgame"] == 0


def test_hidden_triangular_fixed_point(tmp_path: Path) -> None:
    """Ten counters as heaps 6 and 4 settle onto the single staircase position."""
    got = _run_on(tmp_path, [{"id": "t", "heaps": [6, 4]}])
    ref = build_reference([{"id": "t", "heaps": [6, 4]}])
    assert got == ref
    rec = got["openings"]["openings"][0]
    assert rec["endgame"] == [[4, 3, 2, 1]]
    assert rec["endgame_length"] == 1
    assert rec["redeals_to_endgame"] == 2


def test_hidden_arrivals_and_reachability(tmp_path: Path) -> None:
    """Predecessor counts: [2,1] has two, [3] has one, [1,1,1] has none."""
    openings = [
        {"id": "two_one", "heaps": [2, 1]},
        {"id": "single", "heaps": [3]},
        {"id": "spread", "heaps": [1, 1, 1]},
    ]
    got = _run_on(tmp_path, openings)
    assert got == build_reference(openings)
    by_id = {r["id"]: r for r in got["openings"]["openings"]}
    assert by_id["two_one"]["arrivals"] == 2
    assert by_id["single"]["arrivals"] == 1
    assert by_id["spread"]["arrivals"] == 0
    assert by_id["spread"]["reachable"] is False


def test_hidden_small_size_summary(tmp_path: Path) -> None:
    """The size-3 study: 3 positions, 1 unreachable, longest settling 2, one endgame."""
    openings = [{"id": "s", "heaps": [3]}]
    got = _run_on(tmp_path, openings)
    assert got == build_reference(openings)
    size3 = next(r for r in got["sizes"]["sizes"] if r["size"] == 3)
    assert size3["positions"] == 3
    assert size3["unreachable_positions"] == 1
    assert size3["longest_settling"] == 2
    assert size3["endgames"] == [{"cycle": [[2, 1]], "length": 1}]


def test_hidden_order_independence(tmp_path: Path) -> None:
    """Supplying an opening's heaps in any order yields the same canonical record."""
    a = _run_on(tmp_path / "a", [{"id": "z", "heaps": [1, 4, 2, 3]}])
    b = _run_on(tmp_path / "b", [{"id": "z", "heaps": [3, 1, 2, 4]}])
    assert a["openings"] == b["openings"]
    assert a["openings"]["openings"][0]["heaps"] == [4, 3, 2, 1]


def test_hidden_determinism(tmp_path: Path) -> None:
    """Two runs on the same openings produce byte-identical reports."""
    in_dir = tmp_path / "in"
    _write_openings(in_dir, [{"id": "a", "heaps": [5, 3, 2]}, {"id": "b", "heaps": [8]}])
    out_a = tmp_path / "oa"
    out_b = tmp_path / "ob"
    out_a.mkdir()
    out_b.mkdir()
    for out in (out_a, out_b):
        proc = subprocess.run([str(BINARY), str(in_dir), str(out)],
                              capture_output=True, text=True, timeout=300, check=False)
        assert proc.returncode == 0
    for name in ("openings.json", "sizes.json"):
        assert (out_a / name).read_bytes() == (out_b / name).read_bytes()


def test_non_json_entries_are_ignored(tmp_path: Path) -> None:
    """Only top-level .json files are openings; other files and subdirs are skipped."""
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    out_dir.mkdir()
    (in_dir / "keep.json").write_text(json.dumps({"id": "keep", "heaps": [3, 1]}), encoding="utf-8")
    (in_dir / "notes.txt").write_text("not an opening", encoding="utf-8")
    (in_dir / "README").write_text("nor this", encoding="utf-8")
    nested = in_dir / "sub"
    nested.mkdir()
    (nested / "deep.json").write_text(json.dumps({"id": "deep", "heaps": [9]}), encoding="utf-8")
    proc = subprocess.run([str(BINARY), str(in_dir), str(out_dir)],
                          capture_output=True, text=True, timeout=60, check=False)
    assert proc.returncode == 0, f"rc={proc.returncode} stderr={proc.stderr!r}"
    openings = load_json(out_dir / "openings.json")["openings"]
    assert [r["id"] for r in openings] == ["keep"], "only the top-level .json is an opening"


def test_empty_openings_folder_yields_empty_reports(tmp_path: Path) -> None:
    """A folder with no .json openings produces two empty top-level lists, not an error."""
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    out_dir.mkdir()
    (in_dir / "notes.txt").write_text("nothing to study", encoding="utf-8")
    proc = subprocess.run([str(BINARY), str(in_dir), str(out_dir)],
                          capture_output=True, text=True, timeout=60, check=False)
    assert proc.returncode == 0, f"rc={proc.returncode} stderr={proc.stderr!r}"
    assert load_json(out_dir / "openings.json") == {"openings": []}
    assert load_json(out_dir / "sizes.json") == {"sizes": []}


def test_hidden_shared_size_multiple_openings(tmp_path: Path) -> None:
    """Several openings of one total share a single size study computed over all its
    positions, with each opening's own settling landing inside its endgame."""
    openings = [
        {"id": "one_heap", "heaps": [12]},
        {"id": "two_sixes", "heaps": [6, 6]},
        {"id": "three_fours", "heaps": [4, 4, 4]},
        {"id": "all_ones", "heaps": [1] * 12},
    ]
    got = _run_on(tmp_path, openings)
    assert got == build_reference(openings)
    size_recs = [r for r in got["sizes"]["sizes"] if r["size"] == 12]
    assert len(size_recs) == 1, "a shared total is studied exactly once"
    size12 = size_recs[0]
    assert size12["positions"] == partition_count(12)
    opening_recs = got["openings"]["openings"]
    assert {r["counters"] for r in opening_recs} == {12}
    assert size12["longest_settling"] >= max(r["redeals_to_endgame"] for r in opening_recs)
    for r in opening_recs:
        pos = list(r["heaps"])
        for _ in range(r["redeals_to_endgame"]):
            pos = redeal(pos)
        assert pos in r["endgame"], f"{r['id']} does not reach its endgame in the stated moves"


# ---------------------------------------------------------------------------
# Malformed openings
# ---------------------------------------------------------------------------


def _run_raw(tmp_path: Path, files: dict[str, str]) -> subprocess.CompletedProcess[str]:
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (in_dir / name).write_text(text, encoding="utf-8")
    return subprocess.run([str(BINARY), str(in_dir), str(out_dir)],
                          capture_output=True, text=True, timeout=60, check=False)


@pytest.mark.parametrize("name,files", [
    ("invalid_json", {"a.json": "{not valid,"}),
    ("missing_id", {"a.json": json.dumps({"heaps": [3, 1]})}),
    ("empty_id", {"a.json": json.dumps({"id": "", "heaps": [3, 1]})}),
    ("missing_heaps", {"a.json": json.dumps({"id": "a"})}),
    ("heaps_not_array", {"a.json": json.dumps({"id": "a", "heaps": 3})}),
    ("heap_zero", {"a.json": json.dumps({"id": "a", "heaps": [2, 0]})}),
    ("heap_negative", {"a.json": json.dumps({"id": "a", "heaps": [2, -1]})}),
    ("empty_heaps", {"a.json": json.dumps({"id": "a", "heaps": []})}),
    ("heap_not_integer", {"a.json": json.dumps({"id": "a", "heaps": ["2"]})}),
    ("id_not_string", {"a.json": json.dumps({"id": 7, "heaps": [2]})}),
    ("duplicate_id", {
        "a.json": json.dumps({"id": "dup", "heaps": [3]}),
        "b.json": json.dumps({"id": "dup", "heaps": [2, 1]}),
    }),
])
def test_malformed_openings_rejected(tmp_path: Path, name: str, files: dict[str, str]) -> None:
    """Malformed openings cause a non-zero exit."""
    proc = _run_raw(tmp_path, files)
    assert proc.returncode != 0, f"malformed case {name!r} was accepted (rc=0)"


# ---------------------------------------------------------------------------
# Anti-tamper
# ---------------------------------------------------------------------------


def test_openings_tree_unchanged_after_run(binary_run: dict[str, Any]) -> None:
    """The openings folder is untouched after the program runs."""
    assert binary_run["returncode"] == 0
    assert input_tree_hash(OPENINGS_DIR) == EXPECTED_INPUT_TREE_SHA256
