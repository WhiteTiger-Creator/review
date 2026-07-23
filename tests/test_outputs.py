import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import reference as ref

APP = "/app"
BIN = os.path.join(APP, "preorder")

PUBLIC = ref.load_battery("public.jsonl")
HIDDEN = ref.load_battery("hidden.jsonl")
ALL = PUBLIC + HIDDEN

FULL_INPUT = "".join(rec["scenario"].rstrip("\n") + "\n" for rec in ALL)
EXPECTED = [line for rec in ALL for line in rec["expected"]]
PUB_ROWS = sum(len(r["expected"]) for r in PUBLIC)

TOKEN_INCOMP = ref.TOKEN_INCOMP
TOKEN_NONE = ref.TOKEN_NONE
VER_RE = re.compile(r"^\d+\.\d+\.\d+-[0-9A-Za-z.\-]+$")

# The naive/idiomatic readings a strong model reaches for first. Each is the
# retired shortcut or a plausible alternative; every one must diverge from the
# pinned reference on the battery and be visibly wrong on the public examples.
KERNELS = {
    "near": ref.nearrelease_lines,
    "smin": ref.stateless_min_lines,
    "latest": ref.latest_floor_lines,
    "semver": ref.semver_lines,
}


def _build():
    r = subprocess.run(["make", "-C", APP], capture_output=True, text=True)
    return r.returncode == 0 and os.path.exists(BIN)


BUILT = _build()


def _run(text):
    r = subprocess.run([BIN], input=text, capture_output=True, text=True, timeout=180)
    return [ln for ln in r.stdout.splitlines()]


ACTUAL = _run(FULL_INPUT) if BUILT else []


def _kernel_rows(fn, recs):
    out = []
    for rec in recs:
        out.extend(fn(rec["scenario"]))
    return out


PINNED_ALL = _kernel_rows(ref.pinned_lines, ALL)
KERNEL_ALL = {name: _kernel_rows(fn, ALL) for name, fn in KERNELS.items()}
# Per-kernel trap rows: battery indices where the naive reading is wrong.
TRAPS = {
    name: [i for i, (k, e) in enumerate(zip(rows, EXPECTED)) if k != e]
    for name, rows in KERNEL_ALL.items()
}

ROWMETA = []
for rec in ALL:
    sid, evs = ref.parse_block(rec["scenario"])
    qs = [e for e in evs if e[0] == "CMP"]
    for j, (_, qid, va, vb) in enumerate(qs):
        ROWMETA.append(
            {"sid": sid, "qid": qid, "va": va, "vb": vb, "exp": rec["expected"][j]}
        )


def _result(line):
    return line.split("|")[2]


def _scen(*rows, sid="s"):
    return "\n".join(["SCENARIO " + sid] + list(rows) + ["ENDSCENARIO"]) + "\n"


def _expected_for(text):
    """Pinned output for a stream of one or more independent scenarios."""
    blocks, cur = [], []
    for line in text.splitlines():
        p = line.split()
        if p and p[0] == "SCENARIO":
            if cur:
                blocks.append(cur)
            cur = [line]
        elif cur:
            cur.append(line)
    if cur:
        blocks.append(cur)
    out = []
    for b in blocks:
        out.extend(ref.pinned_lines("\n".join(b) + "\n"))
    return out


# ---------------------------------------------------------------------------
# Build + whole-battery conformance
# ---------------------------------------------------------------------------
def test_binary_built():
    """The agent program builds and produces an executable."""
    assert BUILT, "make did not produce /app/preorder"


def test_total_row_count():
    """The program emits exactly one line per CMP query across the battery."""
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


# ---------------------------------------------------------------------------
# Expected == pinned reference; examples mirror the public battery
# ---------------------------------------------------------------------------
def test_public_expected_is_pinned():
    """Committed public expected equals the pinned reference output."""
    for rec in PUBLIC:
        assert rec["expected"] == ref.pinned_lines(rec["scenario"])


def test_hidden_expected_is_pinned():
    """Committed hidden expected equals the pinned reference output."""
    for rec in HIDDEN:
        assert rec["expected"] == ref.pinned_lines(rec["scenario"])


def test_public_slice_matches():
    """The public example rows resolve exactly as shipped."""
    assert ACTUAL[:PUB_ROWS] == EXPECTED[:PUB_ROWS]


def test_examples_match_public_battery():
    """The shipped example files reproduce the public battery byte for byte."""
    for i, rec in enumerate(PUBLIC):
        inp = os.path.join(APP, "data", "examples", "ex%02d.in" % (i + 1))
        outp = os.path.join(APP, "data", "examples", "ex%02d.out" % (i + 1))
        with open(inp) as f:
            got = _run(f.read())
        with open(outp) as f:
            want = [ln for ln in f.read().splitlines()]
        assert got == want == rec["expected"]


# ---------------------------------------------------------------------------
# Idiomatic-adversary divergence: every naive reading is a trap
# ---------------------------------------------------------------------------
def test_pinned_reference_is_ground_truth():
    """The pinned reference reproduces the committed battery."""
    assert PINNED_ALL == EXPECTED


def test_near_release_diverges_on_battery():
    """Ignoring floors and installing the nearest-release build is wrong widely."""
    assert len(TRAPS["near"]) >= 40


def test_stateless_min_diverges_on_battery():
    """Installing the least-mature build but ignoring floors is wrong widely."""
    assert len(TRAPS["smin"]) >= 30


def test_latest_floor_diverges_on_battery():
    """Honouring only the last REQUIRE, not the accumulated floor, is wrong."""
    assert len(TRAPS["latest"]) >= 12


def test_semver_diverges_on_battery():
    """Standard-semver within-tag length (longer higher) is wrong widely."""
    assert len(TRAPS["semver"]) >= 25


def test_no_naive_kernel_scores_full():
    """No naive reading reproduces the whole battery."""
    for name, rows in KERNEL_ALL.items():
        assert rows != EXPECTED, name


def test_program_correct_on_every_trap():
    """On each naive reading's trap rows the program gives the pinned answer."""
    for name, idxs in TRAPS.items():
        for i in idxs:
            assert ACTUAL[i] == EXPECTED[i]
            assert ACTUAL[i] != KERNEL_ALL[name][i]


def test_public_disambiguates_near():
    """At least two public scenarios expose the nearest-release reading as wrong."""
    n = sum(1 for r in PUBLIC if ref.nearrelease_lines(r["scenario"]) != r["expected"])
    assert n >= 2


def test_public_disambiguates_stateless_min():
    """At least two public scenarios expose the floor-ignoring reading as wrong."""
    n = sum(
        1 for r in PUBLIC if ref.stateless_min_lines(r["scenario"]) != r["expected"]
    )
    assert n >= 2


def test_public_disambiguates_latest_floor():
    """At least two public scenarios expose the last-REQUIRE-only reading as wrong."""
    n = sum(1 for r in PUBLIC if ref.latest_floor_lines(r["scenario"]) != r["expected"])
    assert n >= 2


def test_public_disambiguates_semver():
    """At least two public scenarios expose the standard-semver reading as wrong."""
    n = sum(1 for r in PUBLIC if ref.semver_lines(r["scenario"]) != r["expected"])
    assert n >= 2


# ---------------------------------------------------------------------------
# Output-form coverage
# ---------------------------------------------------------------------------
def test_none_rows_present_and_correct():
    """NONE (no candidate clears the floor) appears and resolves exactly."""
    idx = [i for i, ln in enumerate(EXPECTED) if _result(ln) == TOKEN_NONE]
    assert len(idx) >= 5
    for i in idx:
        assert ACTUAL[i] == EXPECTED[i]


def test_incomparable_rows_present_and_correct():
    """INCOMPARABLE appears and resolves exactly."""
    idx = [i for i, ln in enumerate(EXPECTED) if _result(ln) == TOKEN_INCOMP]
    assert len(idx) >= 5
    for i in idx:
        assert ACTUAL[i] == EXPECTED[i]


def test_incomparable_matches_core_mismatch():
    """INCOMPARABLE appears exactly when the two candidate cores differ."""
    for i, m in enumerate(ROWMETA):
        a = ref.parse_version(m["va"])["core"]
        b = ref.parse_version(m["vb"])["core"]
        if a != b:
            assert _result(m["exp"]) == TOKEN_INCOMP
        else:
            assert _result(m["exp"]) != TOKEN_INCOMP


def test_winner_is_verbatim_input():
    """A version result copies one of the two input candidates verbatim."""
    for i, m in enumerate(ROWMETA):
        res = _result(ACTUAL[i])
        if res in (TOKEN_NONE, TOKEN_INCOMP):
            continue
        assert res in (m["va"], m["vb"]), ACTUAL[i]


def test_output_tokens_wellformed():
    """Every result is a valid version string or a defined token."""
    for ln in ACTUAL:
        tok = _result(ln)
        assert tok in (TOKEN_NONE, TOKEN_INCOMP) or VER_RE.match(tok), ln


# ---------------------------------------------------------------------------
# Line format / ordering / determinism / independence
# ---------------------------------------------------------------------------
def test_query_echo_matches():
    """Each output line echoes the queried scenario and query id."""
    for i, m in enumerate(ROWMETA):
        parts = ACTUAL[i].split("|")
        assert parts[0] == m["sid"] and parts[1] == m["qid"], ACTUAL[i]


def test_line_format():
    """Every output line has exactly three fields and no stray whitespace."""
    for ln in ACTUAL:
        assert ln.count("|") == 2 and ln.strip() == ln


def test_no_blank_lines():
    """No output line is empty."""
    assert all(ln != "" for ln in ACTUAL)


def test_scenario_order_preserved():
    """Output lines follow scenario and query order."""
    got = [(ln.split("|")[0], ln.split("|")[1]) for ln in ACTUAL]
    want = [(ln.split("|")[0], ln.split("|")[1]) for ln in EXPECTED]
    assert got == want


def test_determinism_repeat_single():
    """Re-running one scenario yields identical output."""
    rec = HIDDEN[0]
    a = _run(rec["scenario"] + "\n")
    b = _run(rec["scenario"] + "\n")
    assert a == b == rec["expected"]


def test_determinism_full_battery_twice():
    """Re-running the whole battery yields identical output."""
    assert _run(FULL_INPUT) == ACTUAL


def test_each_scenario_independent():
    """Running a scenario in isolation matches its slice of the battery."""
    for rec in ALL[:20]:
        assert _run(rec["scenario"] + "\n") == rec["expected"]


def test_largest_scenario():
    """The largest committed scenario resolves exactly."""
    rec = max(ALL, key=lambda r: len(r["scenario"]))
    assert _run(rec["scenario"] + "\n") == rec["expected"]


def test_state_does_not_cross_scenarios():
    """A REQUIRE in one scenario does not constrain the next."""
    text = _scen("REQUIRE 1.0.0-rc", "CMP q0 1.0.0-alpha 1.0.0-beta", sid="a") + _scen(
        "CMP q0 1.0.0-alpha 1.0.0-beta", sid="b"
    )
    assert _run(text) == ["a|q0|NONE", "b|q0|1.0.0-alpha"]


# ---------------------------------------------------------------------------
# Inline semantic anchors on fresh (non-battery) inputs
# ---------------------------------------------------------------------------
def test_inline_no_floor_installs_least_mature_numeric():
    """With no floor the resolver installs the least-mature (smaller numeric) build."""
    t = _scen("CMP q0 1.4.0-alpha.9 1.4.0-alpha.10")
    assert _run(t) == ["s|q0|1.4.0-alpha.9"] == _expected_for(t)


def test_inline_no_floor_longer_tag_is_less_mature():
    """A longer tag sharing a prefix is less mature, so it is installed with no floor."""
    t = _scen("CMP q0 1.0.0-alpha 1.0.0-alpha.1")
    assert _run(t) == ["s|q0|1.0.0-alpha.1"] == _expected_for(t)


def test_inline_numeric_below_alnum():
    """A numeric identifier is less mature than an alphanumeric one at the same slot."""
    t = _scen("CMP q0 1.0.0-x.2 1.0.0-x.1a")
    assert _run(t) == ["s|q0|1.0.0-x.2"] == _expected_for(t)


def test_inline_floor_blocks_lower_candidate():
    """A REQUIRE floor rejects the candidate below it, installing the one that clears."""
    t = _scen("REQUIRE 1.0.0-beta", "CMP q0 1.0.0-alpha 1.0.0-rc")
    assert _run(t) == ["s|q0|1.0.0-rc"] == _expected_for(t)


def test_inline_floor_yields_none():
    """When no candidate clears the floor the result is NONE."""
    t = _scen("REQUIRE 1.0.0-rc", "CMP q0 1.0.0-alpha 1.0.0-beta")
    assert _run(t) == ["s|q0|NONE"] == _expected_for(t)


def test_inline_floor_accumulates_most_mature():
    """The floor is the most-mature REQUIRE seen, not the latest one."""
    t = _scen(
        "REQUIRE 1.0.0-alpha",
        "REQUIRE 1.0.0-rc",
        "REQUIRE 1.0.0-beta",
        "CMP q0 1.0.0-beta 1.0.0-rc",
    )
    assert _run(t) == ["s|q0|1.0.0-rc"] == _expected_for(t)


def test_inline_floor_minimal_above():
    """Above the floor the resolver installs the least-mature clearing build."""
    t = _scen("REQUIRE 1.0.0-alpha", "CMP q0 1.0.0-beta 1.0.0-rc")
    assert _run(t) == ["s|q0|1.0.0-beta"] == _expected_for(t)


def test_inline_incomparable_core_mismatch():
    """Two versions with different cores resolve to INCOMPARABLE."""
    t = _scen("CMP q0 1.2.0-a 1.3.0-a")
    assert _run(t) == ["s|q0|INCOMPARABLE"] == _expected_for(t)


def test_inline_per_core_floors_independent():
    """Floors are tracked per release line; a floor on one core does not touch another."""
    t = _scen(
        "REQUIRE 1.0.0-rc",
        "CMP q0 2.0.0-alpha 2.0.0-beta",
        "CMP q1 1.0.0-alpha 1.0.0-rc",
    )
    assert _run(t) == ["s|q0|2.0.0-alpha", "s|q1|1.0.0-rc"] == _expected_for(t)


def test_inline_two_scenarios_stream():
    """Two scenarios in one stream each reset resolver state and emit in order."""
    t = _scen("CMP q0 1.0.0-x.9 1.0.0-x.10", sid="a") + _scen(
        "REQUIRE 2.0.0-rc", "CMP q0 2.0.0-beta 2.0.0-rc", sid="b"
    )
    assert _run(t) == ["a|q0|1.0.0-x.9", "b|q0|2.0.0-rc"] == _expected_for(t)


def test_inline_numeric_by_value_not_width():
    """Numeric identifiers compare by value; the least-mature is the smaller value."""
    t = _scen("CMP q0 2.0.0-x.5.9 2.0.0-x.5.12")
    assert _run(t) == ["s|q0|2.0.0-x.5.9"] == _expected_for(t)


def test_min_semantic_cases():
    """The battery executes well over the semantic-case floor."""
    assert len(EXPECTED) >= 60
