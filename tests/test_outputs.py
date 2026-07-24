import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import reference as ref

APP = "/app"
BIN = os.path.join(APP, "resolve")
RV = "v1.0.0"  # root edges are always active regardless of this label

PUBLIC = ref.load_battery("public.jsonl")
HIDDEN = ref.load_battery("hidden.jsonl")
ALL = PUBLIC + HIDDEN

FULL_INPUT = "".join(rec["scenario"].rstrip("\n") + "\n" for rec in ALL)
EXPECTED = [line for rec in ALL for line in rec["expected"]]
PUB_ROWS = sum(len(r["expected"]) for r in PUBLIC)

# Ordered parse of the whole stream, preserving RESET boundaries.
SCEN = ref.parse_stream(FULL_INPUT)
REF_STREAM = ref.pinned_stream(SCEN)
PS_LINES = ref.per_scenario_stream(SCEN)
FL_LINES = ref.flat_stream(SCEN)
IL_LINES = ref.ignore_lock_stream(SCEN)
CI_LINES = ref.cap_ignore_stream(SCEN)
NR_LINES = ref.no_retract_stream(SCEN)

# Row identity (sid, module) for each output line, in order.
ROWMETA = [{"sid": sc["sid"], "mod": m} for sc in SCEN for m in ref.qmods(sc)]

# Naive readings that must each be wrong: independent per-scenario resolution
# (no carry), textbook flatten, dropping the lock floor, ignoring the CAP
# ceilings entirely, and detecting conflicts without retracting dependents.
PER_TRAPS = [i for i in range(len(EXPECTED)) if PS_LINES[i] != REF_STREAM[i]]
FLAT_TRAPS = [i for i in range(len(EXPECTED)) if FL_LINES[i] != REF_STREAM[i]]
LOCK_TRAPS = [i for i in range(len(EXPECTED)) if IL_LINES[i] != REF_STREAM[i]]
CAP_TRAPS = [i for i in range(len(EXPECTED)) if CI_LINES[i] != REF_STREAM[i]]
RETRACT_TRAPS = [i for i in range(len(EXPECTED)) if NR_LINES[i] != REF_STREAM[i]]


def _build():
    r = subprocess.run(["make", "-C", APP], capture_output=True, text=True, check=False)
    return r.returncode == 0 and os.path.exists(BIN)


BUILT = _build()


def _run(text):
    r = subprocess.run(
        [BIN], input=text, capture_output=True, text=True, timeout=120, check=False
    )
    return r.stdout.splitlines()


ACTUAL = _run(FULL_INPUT) if BUILT else []


# -- committed data is internally consistent ---------------------------------


def test_binary_built():
    """The agent program builds and produces an executable."""
    assert BUILT, "make did not produce /app/resolve"


def test_committed_expected_is_reference_stream():
    """Committed expected equals the independently recomputed streamed answer."""
    assert EXPECTED == REF_STREAM


def test_total_row_count():
    """The program emits exactly one line per distinct queried module."""
    assert len(ACTUAL) == len(EXPECTED)


def test_full_battery_matches():
    """Every battery row matches the committed expected line exactly."""
    assert ACTUAL == EXPECTED


def _chunk(k, n=10):
    lo = (len(EXPECTED) * k) // n
    hi = (len(EXPECTED) * (k + 1)) // n
    assert ACTUAL[lo:hi] == EXPECTED[lo:hi]


def test_chunk_0():
    """Battery rows in the first decile match exactly."""
    _chunk(0)


def test_chunk_1():
    """Battery rows in the second decile match exactly."""
    _chunk(1)


def test_chunk_2():
    """Battery rows in the third decile match exactly."""
    _chunk(2)


def test_chunk_3():
    """Battery rows in the fourth decile match exactly."""
    _chunk(3)


def test_chunk_4():
    """Battery rows in the fifth decile match exactly."""
    _chunk(4)


def test_chunk_5():
    """Battery rows in the sixth decile match exactly."""
    _chunk(5)


def test_chunk_6():
    """Battery rows in the seventh decile match exactly."""
    _chunk(6)


def test_chunk_7():
    """Battery rows in the eighth decile match exactly."""
    _chunk(7)


def test_chunk_8():
    """Battery rows in the ninth decile match exactly."""
    _chunk(8)


def test_chunk_9():
    """Battery rows in the tenth decile match exactly."""
    _chunk(9)


def test_public_slice_matches():
    """The public example rows resolve exactly as shipped."""
    assert ACTUAL[:PUB_ROWS] == EXPECTED[:PUB_ROWS]


def test_examples_match_public_sessions():
    """Each shipped example session reproduces its public battery slice."""
    n_sessions = sum(1 for rec in PUBLIC if rec.get("reset"))
    files = sorted(
        f
        for f in os.listdir(os.path.join(APP, "data", "examples"))
        if f.endswith(".in")
    )
    assert len(files) == n_sessions, (len(files), n_sessions)
    idx = 0
    for fn in files:
        got = _run(Path(APP, "data", "examples", fn).read_text(encoding="utf-8"))
        outp = Path(APP, "data", "examples", fn[:-3] + ".out")
        want = outp.read_text(encoding="utf-8").splitlines()
        assert got == want == EXPECTED[idx : idx + len(got)]
        idx += len(got)


# -- identifiability: every naive reading is visibly wrong on public data -----


def _public_diverge(kernel):
    pub = SCEN[: len(PUBLIC)]
    exp = ref.pinned_stream(pub)
    got = kernel(pub)
    return sum(1 for a, b in zip(exp, got, strict=True) if a != b)


def test_per_scenario_diverges_on_public():
    """Independent per-scenario resolution is wrong on several public rows."""
    assert _public_diverge(ref.per_scenario_stream) >= 3


def test_flat_diverges_on_public():
    """Textbook flatten MVS is wrong on at least two public rows."""
    assert _public_diverge(ref.flat_stream) >= 2


def test_lock_diverges_on_public():
    """Dropping the lock floor is wrong on a public row."""
    assert _public_diverge(ref.ignore_lock_stream) >= 1


def test_cap_ignore_diverges_on_public():
    """Ignoring the CAP ceilings is wrong on several public rows."""
    assert _public_diverge(ref.cap_ignore_stream) >= 3


def test_no_retract_diverges_on_public():
    """Marking conflicts without retracting dependents is wrong on public."""
    assert _public_diverge(ref.no_retract_stream) >= 1


def test_per_scenario_scores_zero():
    """A full independent-per-scenario submission fails graded rows."""
    assert PS_LINES != REF_STREAM


def test_flat_scores_zero():
    """A full textbook-flatten submission fails graded rows."""
    assert FL_LINES != REF_STREAM


def test_ignore_lock_scores_zero():
    """A submission that ignores the lock floor fails graded rows."""
    assert IL_LINES != REF_STREAM


def test_cap_ignore_scores_zero():
    """A submission blind to the ceilings fails graded rows."""
    assert CI_LINES != REF_STREAM


def test_no_retract_scores_zero():
    """A submission that never retracts a conflicted provider fails graded rows."""
    assert NR_LINES != REF_STREAM


def test_per_scenario_trap_fraction_in_band():
    """Carry-sensitive rows are a substantial but bounded slice of the battery."""
    frac = len(PER_TRAPS) / len(EXPECTED)
    assert 0.20 <= frac <= 0.45, frac


def test_flat_trap_fraction_in_band():
    """Flatten-trap rows are a substantial but bounded slice of the battery."""
    frac = len(FLAT_TRAPS) / len(EXPECTED)
    assert 0.45 <= frac <= 0.72, frac


def test_cap_trap_fraction_in_band():
    """Ceiling-sensitive rows are a substantial but bounded slice of the battery."""
    frac = len(CAP_TRAPS) / len(EXPECTED)
    assert 0.18 <= frac <= 0.45, frac


def test_program_correct_on_per_scenario_traps():
    """On carry-sensitive rows the program differs from the independent pick."""
    assert len(PER_TRAPS) >= 60
    for i in PER_TRAPS:
        assert ACTUAL[i] == EXPECTED[i]
        assert ACTUAL[i] != PS_LINES[i]


def test_program_correct_on_flat_traps():
    """The program produces the pinned answer on every flatten-trap row."""
    assert len(FLAT_TRAPS) >= 60
    for i in FLAT_TRAPS:
        assert ACTUAL[i] == EXPECTED[i]
        assert ACTUAL[i] != FL_LINES[i]


def test_program_correct_on_lock_traps():
    """On lock-floor traps the chosen version differs from the no-floor pick."""
    assert len(LOCK_TRAPS) >= 20
    for i in LOCK_TRAPS:
        assert ACTUAL[i] == EXPECTED[i]
        assert ACTUAL[i] != IL_LINES[i]


def test_program_correct_on_cap_traps():
    """On ceiling-sensitive rows the program differs from the cap-blind pick."""
    assert len(CAP_TRAPS) >= 60
    for i in CAP_TRAPS:
        assert ACTUAL[i] == EXPECTED[i]
        assert ACTUAL[i] != CI_LINES[i]


def test_program_correct_on_retract_traps():
    """On retraction rows the program differs from the no-retract pick."""
    assert len(RETRACT_TRAPS) >= 25
    for i in RETRACT_TRAPS:
        assert ACTUAL[i] == EXPECTED[i]
        assert ACTUAL[i] != NR_LINES[i]


# -- output shape -------------------------------------------------------------


def test_line_format_wellformed():
    """Each output line is scenario id, module, and a version, NONE or CONFLICT."""
    pat = re.compile(r"^[^|]+\|[^|]+\|(v\d+\.\d+\.\d+|NONE|CONFLICT)$")
    for ln in ACTUAL:
        assert pat.match(ln), ln


def test_module_field_matches_query():
    """Each output line names the sorted queried module in position."""
    for i, m in enumerate(ROWMETA):
        parts = ACTUAL[i].split("|")
        assert parts[0] == m["sid"] and parts[1] == m["mod"]


def test_rows_sorted_within_scenario():
    """Within each scenario the module field is ascending."""
    by_sid = {}
    for ln in ACTUAL:
        sid, mod, _v = ln.split("|")
        by_sid.setdefault(sid, []).append(mod)
    for sid, mods in by_sid.items():
        assert mods == sorted(mods), sid


def test_no_blank_lines():
    """No output line is empty."""
    assert all(ACTUAL)


def test_scenario_order_preserved():
    """Output lines follow scenario order."""
    sids = [ln.split("|", 1)[0] for ln in ACTUAL]
    exp_sids = [ln.split("|", 1)[0] for ln in EXPECTED]
    assert sids == exp_sids


def test_none_token_present():
    """Some queried modules have no reachable edge and print NONE."""
    assert any(ln.endswith("|NONE") for ln in EXPECTED)
    for i, ln in enumerate(ACTUAL):
        if ln.endswith("|NONE"):
            assert EXPECTED[i].endswith("|NONE")


def test_conflict_token_present():
    """Some queried modules are over-constrained and print CONFLICT."""
    assert any(ln.endswith("|CONFLICT") for ln in EXPECTED)
    for i, ln in enumerate(ACTUAL):
        if ln.endswith("|CONFLICT"):
            assert EXPECTED[i].endswith("|CONFLICT")


# -- determinism --------------------------------------------------------------


def test_determinism_full_battery_twice():
    """Re-running the whole battery yields identical output."""
    assert _run(FULL_INPUT) == ACTUAL


def test_largest_scenario_stream():
    """A prefix of the battery through the largest scenario resolves exactly."""
    big = max(range(len(SCEN)), key=lambda i: len(ALL[i]["scenario"]))
    text = "".join(ALL[i]["scenario"].rstrip("\n") + "\n" for i in range(big + 1))
    got = _run(text)
    rows = sum(len(ref.qmods(SCEN[i])) for i in range(big + 1))
    assert got == EXPECTED[:rows]


# -- inline semantic scenarios (self-checked against the reference) ----------


def _render(sc):
    lines = []
    if sc.get("reset_before"):
        lines.append("RESET")
    lines += ["SCENARIO " + sc["sid"], "ROOT " + sc["root"]]
    for u, uv, dep, dv in sc["edges"]:
        lines.append(f"REQ {u} {uv} {dep} {dv}")
    for u, uv, dep, mv in sc.get("caps", []):
        lines.append(f"CAP {u} {uv} {dep} {mv}")
    for m in sorted(sc.get("index", {})):
        lines.append(f"INDEX {m} {' '.join(sc['index'][m])}")
    for m in sorted(sc.get("lock", {})):
        lines.append(f"LOCK {m} {sc['lock'][m]}")
    for q in sc["queries"]:
        lines.append("QUERY " + q)
    lines.append("ENDSCENARIO")
    return "\n".join(lines) + "\n"


def _sc(sid, root, edges, lock, queries, caps=None, reset_before=False):
    return {
        "sid": sid,
        "root": root,
        "edges": edges,
        "caps": caps or [],
        "index": {},
        "lock": lock,
        "queries": queries,
        "reset_before": reset_before,
    }


def _stream(*scs):
    return "".join(_render(sc) for sc in scs)


def test_inline_carry_floor_wins():
    """A version selected earlier in the session floors a later lower pick."""
    a = _sc("s0", "m0", [("m0", RV, "a", "v2.0.0")], {}, ["a"], reset_before=True)
    b = _sc("s1", "m0", [("m0", RV, "a", "v1.0.0")], {}, ["a"])
    out = _run(_stream(a, b))
    assert out == ["s0|a|v2.0.0", "s1|a|v2.0.0"] == ref.pinned_stream([a, b])
    assert out[1] != "s1|a|v1.0.0"


def test_inline_carry_activates_gated_edge():
    """The carried floor lifts a module far enough to fire its own edge."""
    a = _sc("s0", "m0", [("m0", RV, "a", "v1.5.0")], {}, ["a"], reset_before=True)
    b = _sc(
        "s1",
        "m0",
        [("m0", RV, "a", "v1.0.0"), ("a", "v1.5.0", "b", "v3.0.0")],
        {},
        ["a", "b"],
    )
    out = _run(_stream(a, b))
    assert (
        out
        == ["s0|a|v1.5.0", "s1|a|v1.5.0", "s1|b|v3.0.0"]
        == ref.pinned_stream([a, b])
    )


def test_inline_reset_clears_carry():
    """A RESET line drops the session floor so the next scenario starts fresh."""
    a = _sc("s0", "m0", [("m0", RV, "a", "v2.0.0")], {}, ["a"], reset_before=True)
    b = _sc("s1", "m0", [("m0", RV, "a", "v1.0.0")], {}, ["a"], reset_before=True)
    out = _run(_stream(a, b))
    assert out == ["s0|a|v2.0.0", "s1|a|v1.0.0"] == ref.pinned_stream([a, b])


def test_inline_carry_only_for_built_modules():
    """A module that never enters a build list carries no floor forward."""
    a = _sc(
        "s0",
        "m0",
        [("m0", RV, "a", "v1.0.0"), ("side", "v1.0.0", "z", "v9.0.0")],
        {},
        ["a"],
        reset_before=True,
    )
    b = _sc("s1", "m0", [("m0", RV, "z", "v1.0.0")], {}, ["z"])
    out = _run(_stream(a, b))
    assert out == ["s0|a|v1.0.0", "s1|z|v1.0.0"] == ref.pinned_stream([a, b])


def test_inline_dormant_edge_unreachable():
    """An edge declared by an unreached version leaves its dep unreachable."""
    sc = _sc(
        "s2",
        "m0",
        [("m0", RV, "u", "v1.0.0"), ("u", "v2.0.0", "w", "v6.0.0")],
        {},
        ["u", "w"],
        reset_before=True,
    )
    out = _run(_render(sc))
    assert out == ["s2|u|v1.0.0", "s2|w|NONE"] == ref.pinned_one(sc)


def test_inline_lock_floor_raises():
    """A lock entry above the recomputed pick acts as a floor and wins."""
    sc = _sc(
        "s3",
        "m0",
        [("m0", RV, "x", "v1.2.0")],
        {"x": "v2.5.0"},
        ["x"],
        reset_before=True,
    )
    out = _run(_render(sc))
    assert out == ["s3|x|v2.5.0"] == ref.pinned_one(sc)


def test_inline_stale_lock_below_ignored():
    """A lock entry below the recomputed pick is ignored, not trusted."""
    sc = _sc(
        "s4",
        "m0",
        [("m0", RV, "x", "v2.0.0")],
        {"x": "v1.0.0"},
        ["x"],
        reset_before=True,
    )
    out = _run(_render(sc))
    assert out == ["s4|x|v2.0.0"] == ref.pinned_one(sc)


def test_inline_diamond_maxima():
    """A diamond where both arms require one module selects the higher requirement."""
    sc = _sc(
        "s5",
        "m0",
        [
            ("m0", RV, "a", "v1.0.0"),
            ("m0", RV, "b", "v1.0.0"),
            ("a", "v1.0.0", "c", "v1.3.0"),
            ("b", "v1.0.0", "c", "v1.7.0"),
        ],
        {},
        ["c"],
        reset_before=True,
    )
    assert _run(_render(sc)) == ["s5|c|v1.7.0"] == ref.pinned_one(sc)


def test_inline_cascade_iterates():
    """Raising a module activates its own higher-version edge in a later pass."""
    sc = _sc(
        "s6",
        "m0",
        [
            ("m0", RV, "a", "v1.0.0"),
            ("m0", RV, "c", "v1.0.0"),
            ("c", "v1.0.0", "a", "v2.0.0"),
            ("a", "v2.0.0", "b", "v1.5.0"),
            ("a", "v3.0.0", "d", "v7.0.0"),
        ],
        {},
        ["a", "b", "d"],
        reset_before=True,
    )
    assert (
        _run(_render(sc))
        == ["s6|a|v2.0.0", "s6|b|v1.5.0", "s6|d|NONE"]
        == ref.pinned_one(sc)
    )


def test_inline_numeric_field_width():
    """Version fields compare numerically, not lexically, across widths."""
    sc = _sc(
        "s7",
        "m0",
        [
            ("m0", RV, "m1", "v1.0.9"),
            ("m0", RV, "m2", "v0.1.0"),
            ("m2", "v0.1.0", "m1", "v1.0.12"),
        ],
        {},
        ["m1"],
        reset_before=True,
    )
    assert _run(_render(sc)) == ["s7|m1|v1.0.12"] == ref.pinned_one(sc)


def test_inline_self_and_cycle_terminate():
    """A self edge and a back edge terminate with a well-defined selection."""
    sc = _sc(
        "s8",
        "m0",
        [
            ("m0", RV, "a", "v1.0.0"),
            ("a", "v1.0.0", "a", "v1.0.0"),
            ("a", "v1.0.0", "b", "v12.3.10"),
            ("b", "v12.3.10", "a", "v1.0.0"),
        ],
        {},
        ["a", "b"],
        reset_before=True,
    )
    assert _run(_render(sc)) == ["s8|a|v1.0.0", "s8|b|v12.3.10"] == ref.pinned_one(sc)


def test_inline_cap_over_constrained():
    """A module demanded above its ceiling is CONFLICT."""
    sc = _sc(
        "s9",
        "m0",
        [("m0", RV, "a", "v5.0.0")],
        {},
        ["a"],
        caps=[("m0", RV, "a", "v3.0.0")],
        reset_before=True,
    )
    assert _run(_render(sc)) == ["s9|a|CONFLICT"] == ref.pinned_one(sc)


def test_inline_cap_slack_does_not_bite():
    """A ceiling above the demand leaves the selection unchanged."""
    sc = _sc(
        "s10",
        "m0",
        [("m0", RV, "a", "v2.0.0")],
        {},
        ["a"],
        caps=[("m0", RV, "a", "v5.0.0")],
        reset_before=True,
    )
    assert _run(_render(sc)) == ["s10|a|v2.0.0"] == ref.pinned_one(sc)


def test_inline_cap_retracts_dependent():
    """A capped-out module retracts its edge, dropping its dependent to NONE."""
    sc = _sc(
        "s11",
        "m0",
        [("m0", RV, "a", "v2.0.0"), ("a", "v2.0.0", "c", "v9.0.0")],
        {},
        ["a", "c"],
        caps=[("m0", RV, "a", "v1.0.0")],
        reset_before=True,
    )
    assert _run(_render(sc)) == ["s11|a|CONFLICT", "s11|c|NONE"] == ref.pinned_one(sc)


def test_inline_cap_gated_by_declarer():
    """A ceiling gated on version U bites only once its declarer reaches U."""
    sc = _sc(
        "s12",
        "m0",
        [("m0", RV, "x", "v2.0.0"), ("m0", RV, "y", "v3.0.0")],
        {},
        ["x", "y"],
        caps=[("x", "v2.0.0", "y", "v1.0.0")],
        reset_before=True,
    )
    assert _run(_render(sc)) == ["s12|x|v2.0.0", "s12|y|CONFLICT"] == ref.pinned_one(sc)


def test_inline_cap_retract_keeps_sibling_low():
    """Retracting a conflicted provider leaves a sibling at its direct demand."""
    sc = _sc(
        "s13",
        "m0",
        [
            ("m0", RV, "a", "v2.0.0"),
            ("m0", RV, "b", "v1.0.0"),
            ("a", "v2.0.0", "b", "v8.0.0"),
        ],
        {},
        ["a", "b"],
        caps=[("m0", RV, "a", "v1.0.0")],
        reset_before=True,
    )
    assert _run(_render(sc)) == ["s13|a|CONFLICT", "s13|b|v1.0.0"] == ref.pinned_one(sc)


def test_inline_carry_then_cap_conflict():
    """A carried floor above a later ceiling makes the module CONFLICT."""
    a = _sc("s14", "m0", [("m0", RV, "a", "v2.0.0")], {}, ["a"], reset_before=True)
    b = _sc(
        "s15",
        "m0",
        [("m0", RV, "a", "v1.0.0")],
        {},
        ["a"],
        caps=[("m0", RV, "a", "v1.5.0")],
    )
    out = _run(_stream(a, b))
    assert out == ["s14|a|v2.0.0", "s15|a|CONFLICT"] == ref.pinned_stream([a, b])


def test_hidden_generalization_recomputed():
    """Every hidden row matches the independently recomputed streamed reference."""
    hid = SCEN[len(PUBLIC) :]
    assert ref.pinned_stream(hid) == EXPECTED[PUB_ROWS:]
    text = "".join(rec["scenario"].rstrip("\n") + "\n" for rec in HIDDEN)
    assert _run(text) == EXPECTED[PUB_ROWS:]


def test_no_forbidden_import():
    """No agent-visible source vendors x/mod or another whole-rule resolver helper."""
    banned = ["golang.org/x/mod", "modfile", "pubgrub", "hashicorp/go-version"]
    hits = []
    for root, _dirs, files in os.walk(APP):
        if "/data" in root or "/docs" in root:
            continue
        for fn in files:
            if fn.endswith((".go", ".mod", ".sum")):
                text = Path(root, fn).read_text(encoding="utf-8").lower()
                hits.extend((fn, b) for b in banned if b in text)
    assert hits == [], hits


def test_min_semantic_cases():
    """The battery executes well over the semantic-case floor."""
    assert len(EXPECTED) >= 60
