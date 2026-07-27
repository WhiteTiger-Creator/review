import json
import os
import re
import subprocess
import sys
from fractions import Fraction

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_DIR)
import cartref as R

APP = os.environ.get("QUILL_APP", "/app")
DATA_DIR = os.path.join(APP, "data")
SRC_DIR = os.path.join(APP, "src")
EX_DIR = os.path.join(APP, "examples")
FIT_DIR = os.environ.get("QUILL_FIT", "/tmp/quill_cart_fit")
BINARY = os.path.join(FIT_DIR, "cart")
BATTERY = os.path.join(TESTS_DIR, "battery")
HIDDEN = os.path.join(TESTS_DIR, "hidden")
HIDDEN_DATA = os.path.join(HIDDEN, "data")

LINE_RE = re.compile(
    r"^\S+ (?:"
    r"V \d+ P \d+/\d+ S \d+/\d+"
    r"|Q \d+ C \d+ N \d+ I \d+/\d+ E \d+/\d+ D \d+/\d+(?: \d+/\d+)*"
    r"|G \d+ R \d+ V \d+ T -?\d+ D [FV] A \d+/\d+"
    r"|D \d+ V \d+ T -?\d+ N \d+ G \d+/\d+"
    r"|REJECT"
    r")$"
)

FORBIDDEN = ("mlpack", "dlib", "opencv2/ml", "shark/", "xgboost", "lightgbm")


def _read_lines(path):
    with open(path, encoding="utf-8") as fh:
        return [ln.rstrip("\n") for ln in fh if ln.strip() != ""]


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _group(lines):
    groups = {}
    for ln in lines:
        groups.setdefault(ln.split(" ", 1)[0], []).append(ln)
    return groups


def _compile():
    os.makedirs(FIT_DIR, exist_ok=True)
    return subprocess.run(
        [
            "g++",
            "-std=c++17",
            "-O2",
            "-o",
            BINARY,
            os.path.join(SRC_DIR, "main.cpp"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _run(data_dir, queries_path):
    proc = subprocess.run(
        [BINARY, data_dir, queries_path],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError("agent run failed: " + proc.stderr[-2000:])
    return [ln for ln in proc.stdout.split("\n") if ln.strip() != ""]


def _chunks(seq, count):
    size = max(1, (len(seq) + count - 1) // count)
    return [seq[i : i + size] for i in range(0, len(seq), size)]


COMPILE = _compile()
FIT_OK = COMPILE.returncode == 0 and os.path.exists(BINARY)

TABLES = R.read_tables(DATA_DIR)
HTABLES = R.read_tables(HIDDEN_DATA)

QUERY_LINES = _read_lines(os.path.join(BATTERY, "queries.txt"))
GOLDEN_LINES = _read_lines(os.path.join(BATTERY, "expected.txt"))
FAMILY = _read_json(os.path.join(BATTERY, "families.json"))

HQUERY_LINES = _read_lines(os.path.join(HIDDEN, "queries.txt"))
HGOLDEN_LINES = _read_lines(os.path.join(HIDDEN, "expected.txt"))
HFAMILY = _read_json(os.path.join(HIDDEN, "families.json"))

REF_LINES = R.process(TABLES, QUERY_LINES)
REF_BY_QID = _group(REF_LINES)
HREF_LINES = R.process(HTABLES, HQUERY_LINES)
HREF_BY_QID = _group(HREF_LINES)

QUERY_BY_QID = {ln.split()[0]: ln.split() for ln in QUERY_LINES}

if FIT_OK:
    AGENT_LINES = _run(DATA_DIR, os.path.join(BATTERY, "queries.txt"))
    HAGENT_LINES = _run(HIDDEN_DATA, os.path.join(HIDDEN, "queries.txt"))
else:
    AGENT_LINES = []
    HAGENT_LINES = []
AGENT_BY_QID = _group(AGENT_LINES)
HAGENT_BY_QID = _group(HAGENT_LINES)


def _qids(family, table):
    return sorted(q for q, f in table.items() if f == family)


BULK_QIDS = _qids("bulk", FAMILY)
POOL_QIDS = _qids("nodebase", FAMILY)
READING_QIDS = _qids("fwdonly", FAMILY)
STRICT_QIDS = _qids("nonneg", FAMILY)
DEFAULT_QIDS = _qids("leftfall", FAMILY)
REJECT_QIDS = _qids("reject", FAMILY)
HIDDEN_QIDS = sorted(HFAMILY)

DECOY = {
    v: _group(R.process(TABLES, QUERY_LINES, v)) for v in R.VARIANTS if v != "pinned"
}


def _assert_group(qids, agent_map, ref_map):
    for qid in qids:
        assert agent_map.get(qid) == ref_map.get(qid), qid


def test_model_sources_are_usable():
    """The agent source compiles cleanly."""
    assert FIT_OK, COMPILE.stderr[-2000:]


def test_reference_matches_committed_golden():
    """Independent rational recomputation equals the committed visible battery."""
    assert REF_LINES == GOLDEN_LINES


def test_hidden_reference_matches_committed_golden():
    """Independent rational recomputation equals the committed hidden battery."""
    assert HREF_LINES == HGOLDEN_LINES


def test_visible_line_count():
    """The agent emits exactly the expected number of visible battery lines."""
    assert len(AGENT_LINES) == len(REF_LINES)


def test_hidden_line_count():
    """The agent emits exactly the expected number of hidden battery lines."""
    assert len(HAGENT_LINES) == len(HREF_LINES)


def test_every_visible_query_present():
    """The agent produces an output block for every visible query id."""
    assert set(AGENT_BY_QID) == set(REF_BY_QID)


def test_every_hidden_query_present():
    """The agent produces an output block for every hidden query id."""
    assert set(HAGENT_BY_QID) == set(HREF_BY_QID)


@pytest.mark.parametrize("idx", range(20))
def test_bulk_slice_matches(idx):
    """The agent reproduces a slice of the ordinary bulk battery exactly."""
    chunks = _chunks(BULK_QIDS, 20)
    if idx >= len(chunks):
        pytest.skip("no chunk")
    _assert_group(chunks[idx], AGENT_BY_QID, REF_BY_QID)


@pytest.mark.parametrize("idx", range(3))
def test_association_pool_slice_matches(idx):
    """The agent reproduces tables with heavy gaps in the deciding feature."""
    chunks = _chunks(POOL_QIDS, 3)
    if idx >= len(chunks):
        pytest.skip("no chunk")
    _assert_group(chunks[idx], AGENT_BY_QID, REF_BY_QID)


@pytest.mark.parametrize("idx", range(3))
def test_reversed_reading_slice_matches(idx):
    """The agent reproduces tables where a reversed stand-in reading wins."""
    chunks = _chunks(READING_QIDS, 3)
    if idx >= len(chunks):
        pytest.skip("no chunk")
    _assert_group(chunks[idx], AGENT_BY_QID, REF_BY_QID)


@pytest.mark.parametrize("idx", range(3))
def test_zero_association_slice_matches(idx):
    """The agent reproduces tables where a stand-in only ties the default branch."""
    chunks = _chunks(STRICT_QIDS, 3)
    if idx >= len(chunks):
        pytest.skip("no chunk")
    _assert_group(chunks[idx], AGENT_BY_QID, REF_BY_QID)


@pytest.mark.parametrize("idx", range(3))
def test_default_branch_slice_matches(idx):
    """The agent reproduces tables whose rows fall through to the default branch."""
    chunks = _chunks(DEFAULT_QIDS, 3)
    if idx >= len(chunks):
        pytest.skip("no chunk")
    _assert_group(chunks[idx], AGENT_BY_QID, REF_BY_QID)


def test_refused_queries_match():
    """The agent refuses exactly the queries the contract refuses."""
    _assert_group(REJECT_QIDS, AGENT_BY_QID, REF_BY_QID)


@pytest.mark.parametrize("idx", range(8))
def test_hidden_slice_matches(idx):
    """The agent generalizes to a held back battery over unseen tables."""
    chunks = _chunks(HIDDEN_QIDS, 8)
    if idx >= len(chunks):
        pytest.skip("no chunk")
    _assert_group(chunks[idx], HAGENT_BY_QID, HREF_BY_QID)


def test_line_schema_is_canonical():
    """Every emitted line matches the canonical output grammar."""
    bad = [ln for ln in AGENT_LINES + HAGENT_LINES if not LINE_RE.match(ln)]
    assert bad[:5] == []


def test_fractions_are_in_lowest_terms():
    """Every reported quantity is a reduced fraction with a positive denominator."""
    bad = []
    for ln in AGENT_LINES:
        parts = ln.split()
        if parts[1] == "V":
            tokens = [parts[4], parts[6]]
        elif parts[1] == "Q":
            tokens = [parts[8], parts[10], *parts[12:]]
        else:
            continue
        for token in tokens:
            num, den = token.split("/")
            value = Fraction(int(num), int(den))
            if int(den) <= 0 or f"{value.numerator}/{value.denominator}" != token:
                bad.append(ln)
    assert bad[:5] == []


def test_one_summary_line_per_feature():
    """Each query reports one feature summary per column, in increasing order."""
    bad = []
    for qid, lines in AGENT_BY_QID.items():
        query = QUERY_BY_QID[qid]
        if len(query) != 5 or query[1] not in TABLES or lines == [f"{qid} REJECT"]:
            continue
        seen = [int(ln.split()[2]) for ln in lines if ln.split()[1] == "V"]
        if seen != list(range(len(TABLES[query[1]][0][0]))):
            bad.append(qid)
    assert bad[:5] == []


def test_one_report_line_per_held_out_example():
    """Each held out example gets exactly one report line, in row order."""
    bad = []
    for qid, lines in AGENT_BY_QID.items():
        query = QUERY_BY_QID[qid]
        if len(query) != 5 or query[2] not in TABLES or lines == [f"{qid} REJECT"]:
            continue
        seen = [int(ln.split()[2]) for ln in lines if ln.split()[1] == "Q"]
        if seen != list(range(len(TABLES[query[2]]))):
            bad.append(qid)
    assert bad[:5] == []


def test_class_distribution_sums_to_one():
    """The reported class distribution of every terminal group sums to one."""
    bad = []
    for ln in AGENT_LINES:
        parts = ln.split()
        if parts[1] != "Q":
            continue
        total = sum(
            Fraction(int(t.split("/")[0]), int(t.split("/")[1])) for t in parts[12:]
        )
        if total != 1:
            bad.append(ln)
    assert bad[:5] == []


def test_predicted_class_is_a_plurality_of_its_group():
    """The predicted class holds the largest share of its terminal group."""
    bad = []
    for ln in AGENT_LINES:
        parts = ln.split()
        if parts[1] != "Q":
            continue
        shares = [
            Fraction(int(t.split("/")[0]), int(t.split("/")[1])) for t in parts[12:]
        ]
        predicted = int(parts[4])
        if predicted >= len(shares) or shares[predicted] != max(shares):
            bad.append(ln)
    assert bad[:5] == []


def test_lowest_class_wins_a_share_tie():
    """When two classes share the largest slice the lower numbered class is predicted."""
    bad = []
    for ln in AGENT_LINES:
        parts = ln.split()
        if parts[1] != "Q":
            continue
        shares = [
            Fraction(int(t.split("/")[0]), int(t.split("/")[1])) for t in parts[12:]
        ]
        if int(parts[4]) != shares.index(max(shares)):
            bad.append(ln)
    assert bad[:5] == []


def test_impurity_matches_the_reported_distribution():
    """The reported impurity equals one minus the summed squared class shares."""
    bad = []
    for ln in AGENT_LINES:
        parts = ln.split()
        if parts[1] != "Q":
            continue
        shares = [
            Fraction(int(t.split("/")[0]), int(t.split("/")[1])) for t in parts[12:]
        ]
        want = 1 - sum(s * s for s in shares)
        got = Fraction(int(parts[8].split("/")[0]), int(parts[8].split("/")[1]))
        if got != want:
            bad.append(ln)
    assert bad[:5] == []


def test_support_count_is_consistent_with_the_distribution():
    """Every class share is an exact multiple of one over the reported support count."""
    bad = []
    for ln in AGENT_LINES:
        parts = ln.split()
        if parts[1] != "Q":
            continue
        support = int(parts[6])
        if support < 1:
            bad.append(ln)
            continue
        for token in parts[12:]:
            share = Fraction(int(token.split("/")[0]), int(token.split("/")[1]))
            if (share * support).denominator != 1:
                bad.append(ln)
    assert bad[:5] == []


def test_evidence_stays_within_its_range():
    """Reported evidence is never below zero nor above one."""
    bad = []
    for ln in AGENT_LINES:
        parts = ln.split()
        if parts[1] != "Q":
            continue
        value = Fraction(int(parts[10].split("/")[0]), int(parts[10].split("/")[1]))
        if value < 0 or value > 1:
            bad.append(ln)
    assert bad[:5] == []


def test_complete_examples_report_full_evidence():
    """An example with every measurement recorded is placed on full evidence."""
    bad = []
    for qid, lines in AGENT_BY_QID.items():
        query = QUERY_BY_QID[qid]
        if len(query) != 5 or query[2] not in TABLES:
            continue
        probes = TABLES[query[2]]
        for ln in lines:
            parts = ln.split()
            if parts[1] != "Q":
                continue
            row = probes[int(parts[2])][0]
            if all(v != -1 for v in row) and parts[10] != "1/1":
                bad.append(ln)
    assert bad[:5] == []


def test_importance_is_never_negative():
    """No feature reports a negative contribution in either role."""
    bad = []
    for ln in AGENT_LINES:
        parts = ln.split()
        if parts[1] != "V":
            continue
        for token in (parts[4], parts[6]):
            if Fraction(int(token.split("/")[0]), int(token.split("/")[1])) < 0:
                bad.append(ln)
    assert bad[:5] == []


def test_some_feature_carries_primary_importance():
    """Any query whose model splits at least once credits a primary contributor."""
    bad = []
    for qid, lines in AGENT_BY_QID.items():
        summaries = [ln for ln in lines if ln.split()[1] == "V"]
        reports = [ln for ln in lines if ln.split()[1] == "Q"]
        if not summaries or not reports:
            continue
        distinct = {ln.split()[4] for ln in reports}
        totals = [
            Fraction(int(ln.split()[4].split("/")[0]), int(ln.split()[4].split("/")[1]))
            for ln in summaries
        ]
        if len(distinct) > 1 and sum(totals) == 0:
            bad.append(qid)
    assert bad[:5] == []


def test_visible_run_is_deterministic():
    """Re-running the agent on the visible battery yields identical output."""
    assert _run(DATA_DIR, os.path.join(BATTERY, "queries.txt")) == AGENT_LINES


def test_hidden_run_is_deterministic():
    """Re-running the agent on the hidden battery yields identical output."""
    assert _run(HIDDEN_DATA, os.path.join(HIDDEN, "queries.txt")) == HAGENT_LINES


def test_worked_examples_are_reproduced():
    """The agent reproduces every shipped worked example byte for byte."""
    bad = []
    for name in sorted(os.listdir(EX_DIR)):
        if not name.endswith(".in"):
            continue
        got = _run(DATA_DIR, os.path.join(EX_DIR, name))
        want = _read_lines(os.path.join(EX_DIR, name[:-3] + ".out"))
        if got != want:
            bad.append(name)
    assert bad == []


def test_no_forbidden_ml_dependency():
    """The agent tree includes no bundled machine-learning library."""
    blob = ""
    for root, _dirs, files in os.walk(SRC_DIR):
        for name in sorted(files):
            with open(
                os.path.join(root, name), encoding="utf-8", errors="ignore"
            ) as fh:
                blob += fh.read().lower()
    assert [t for t in FORBIDDEN if t in blob] == []


@pytest.mark.parametrize(
    ("variant", "family"),
    [
        ("nodebase", "nodebase"),
        ("nodebase", "nonneg"),
        ("fwdonly", "fwdonly"),
        ("fwdonly", "nodebase"),
        ("nonneg", "nonneg"),
        ("leftfall", "leftfall"),
    ],
)
def test_plausible_variant_fails_its_trap_family(variant, family):
    """A plausible alternative convention is wrong on the family that traps it."""
    qids = _qids(family, FAMILY)
    wrong = [q for q in qids if DECOY[variant].get(q) != REF_BY_QID.get(q)]
    assert wrong, (variant, family)


def _reported(block):
    return [ln for ln in block if ln.split()[1] not in ("G", "D")]


@pytest.mark.parametrize("variant", sorted(DECOY))
def test_plausible_variant_is_clean_on_bulk(variant):
    """Every alternative convention agrees on the ordinary summary and per example rows."""
    wrong = [
        q
        for q in BULK_QIDS
        if _reported(DECOY[variant].get(q, [])) != _reported(REF_BY_QID.get(q, []))
    ]
    assert wrong == []


@pytest.mark.parametrize("variant", sorted(DECOY))
def test_plausible_variant_is_caught_by_the_stand_in_report(variant):
    """Reporting the ranked stand-ins exposes every alternative convention."""
    wrong = [
        q
        for q in sorted(DECOY[variant])
        if [ln for ln in DECOY[variant][q] if ln.split()[1] == "G"]
        != [ln for ln in REF_BY_QID.get(q, []) if ln.split()[1] == "G"]
    ]
    assert wrong


@pytest.mark.parametrize("variant", sorted(DECOY))
def test_plausible_variant_scores_zero_overall(variant):
    """Every plausible alternative convention fails the all-pass battery."""
    flat = [ln for qid in sorted(DECOY[variant]) for ln in DECOY[variant][qid]]
    assert flat != REF_LINES


def test_refusal_token_is_the_only_output():
    """A refused query emits its refusal token and nothing else."""
    for qid in REJECT_QIDS:
        assert AGENT_BY_QID.get(qid) == [f"{qid} REJECT"]


def test_terminal_support_is_within_the_training_table():
    """Every terminal group holds between one row and the whole training table."""
    bad = []
    for qid, lines in AGENT_BY_QID.items():
        query = QUERY_BY_QID[qid]
        if len(query) != 5 or query[1] not in TABLES:
            continue
        rows = len(TABLES[query[1]])
        for ln in lines:
            parts = ln.split()
            if parts[1] == "Q" and not 1 <= int(parts[6]) <= rows:
                bad.append(ln)
    assert bad[:5] == []


def test_battery_covers_enough_distinct_cases():
    """The executed battery carries well over the required number of semantic cases."""
    assert len(QUERY_LINES) + len(HQUERY_LINES) >= 60
    assert len(set(FAMILY.values())) >= 5


def _stand_ins(lines):
    return [ln.split() for ln in lines if ln.split()[1] == "G"]


def test_stand_in_ranks_start_at_one_and_are_contiguous():
    """Each node's stand-in ranks run one, two, three with no gaps."""
    bad = []
    for qid, lines in AGENT_BY_QID.items():
        per_node = {}
        for g in _stand_ins(lines):
            per_node.setdefault(int(g[2]), []).append(int(g[4]))
        for node, ranks in per_node.items():
            if ranks != list(range(1, len(ranks) + 1)):
                bad.append((qid, node))
    assert bad[:5] == []


def test_stand_in_associations_are_ranked_downward():
    """Within a node the associations never increase as the rank grows."""
    bad = []
    for qid, lines in AGENT_BY_QID.items():
        per_node = {}
        for g in _stand_ins(lines):
            num, den = g[12].split("/")
            per_node.setdefault(int(g[2]), []).append(Fraction(int(num), int(den)))
        for node, scores in per_node.items():
            if scores != sorted(scores, reverse=True):
                bad.append((qid, node))
    assert bad[:5] == []


def test_stand_in_association_is_strictly_positive():
    """A stand-in that fails to beat the default branch is never reported."""
    bad = []
    for g in (g for lines in AGENT_BY_QID.values() for g in _stand_ins(lines)):
        num, den = g[12].split("/")
        if Fraction(int(num), int(den)) <= 0:
            bad.append(" ".join(g))
    assert bad[:5] == []


def test_a_node_lists_each_feature_at_most_once():
    """A node never keeps two stand-ins built on the same measurement."""
    bad = []
    for qid, lines in AGENT_BY_QID.items():
        seen = {}
        for g in _stand_ins(lines):
            key = (int(g[2]), int(g[6]))
            if key in seen:
                bad.append((qid, key))
            seen[key] = True
    assert bad[:5] == []


@pytest.mark.parametrize("idx", range(6))
def test_stand_in_slice_matches(idx):
    """The agent reproduces the ranked stand-ins of the visible battery."""
    qids = sorted(REF_BY_QID)
    chunks = _chunks(qids, 6)
    if idx >= len(chunks):
        pytest.skip("no chunk")
    for qid in chunks[idx]:
        got = [ln for ln in AGENT_BY_QID.get(qid, []) if ln.split()[1] == "G"]
        want = [ln for ln in REF_BY_QID.get(qid, []) if ln.split()[1] == "G"]
        assert got == want, qid


@pytest.mark.parametrize("idx", range(4))
def test_hidden_stand_in_slice_matches(idx):
    """The agent generalizes the ranked stand-ins to unseen tables."""
    qids = sorted(HREF_BY_QID)
    chunks = _chunks(qids, 4)
    if idx >= len(chunks):
        pytest.skip("no chunk")
    for qid in chunks[idx]:
        got = [ln for ln in HAGENT_BY_QID.get(qid, []) if ln.split()[1] == "G"]
        want = [ln for ln in HREF_BY_QID.get(qid, []) if ln.split()[1] == "G"]
        assert got == want, qid


def _splits(lines):
    return [ln.split() for ln in lines if ln.split()[1] == "D"]


def test_every_node_with_stand_ins_is_a_reported_split():
    """A node that lists stand-ins must also report the split it makes."""
    bad = []
    for qid, lines in AGENT_BY_QID.items():
        split_ids = {int(d[2]) for d in _splits(lines)}
        stand_in_ids = {int(g[2]) for g in _stand_ins(lines)}
        if not stand_in_ids <= split_ids:
            bad.append(qid)
    assert bad[:5] == []


def test_split_sizes_shrink_down_the_tree():
    """A node numbered later in its own subtree can never hold more rows than its root."""
    bad = []
    for qid, lines in AGENT_BY_QID.items():
        rows = _splits(lines)
        if not rows:
            continue
        root = min(int(d[2]) for d in rows)
        top = next(int(d[8]) for d in rows if int(d[2]) == root)
        if any(int(d[8]) > top for d in rows):
            bad.append(qid)
    assert bad[:5] == []


def test_split_gain_is_strictly_positive():
    """A split is only made when it removes impurity, so every reported gain exceeds zero."""
    bad = []
    for d in (d for lines in AGENT_BY_QID.values() for d in _splits(lines)):
        num, den = d[10].split("/")
        if Fraction(int(num), int(den)) <= 0:
            bad.append(" ".join(d))
    assert bad[:5] == []


@pytest.mark.parametrize("idx", range(6))
def test_split_slice_matches(idx):
    """The agent reproduces every split the fit makes over the visible battery."""
    qids = sorted(REF_BY_QID)
    chunks = _chunks(qids, 6)
    if idx >= len(chunks):
        pytest.skip("no chunk")
    for qid in chunks[idx]:
        got = [ln for ln in AGENT_BY_QID.get(qid, []) if ln.split()[1] == "D"]
        want = [ln for ln in REF_BY_QID.get(qid, []) if ln.split()[1] == "D"]
        assert got == want, qid


@pytest.mark.parametrize("idx", range(4))
def test_hidden_split_slice_matches(idx):
    """The agent generalizes its splits to unseen tables."""
    qids = sorted(HREF_BY_QID)
    chunks = _chunks(qids, 4)
    if idx >= len(chunks):
        pytest.skip("no chunk")
    for qid in chunks[idx]:
        got = [ln for ln in HAGENT_BY_QID.get(qid, []) if ln.split()[1] == "D"]
        want = [ln for ln in HREF_BY_QID.get(qid, []) if ln.split()[1] == "D"]
        assert got == want, qid


BUDGET_IR = 1_200_000_000
REFERENCE_DIR = "/tests/references"


def _budget_workload(root):
    """Deterministically write the fixed workload the instruction budget is set on."""
    import random

    rnd = random.Random(11)
    rows, features, values, classes, probes = 900, 14, 40, 3, 200
    os.makedirs(root, exist_ok=True)

    def table(path, count):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(",".join(f"f{j}" for j in range(features)) + ",label\n")
            lines = []
            for _ in range(count):
                cells = []
                for _j in range(features):
                    value = rnd.randrange(values)
                    cells.append(-1 if rnd.random() < 0.18 else value)
                cells.append(rnd.randrange(classes))
                lines.append(",".join(str(c) for c in cells) + "\n")
            fh.writelines(lines)

    table(os.path.join(root, "bigtrain.csv"), rows)
    table(os.path.join(root, "bigprobe.csv"), probes)
    queries = os.path.join(root, "queries.txt")
    with open(queries, "w", encoding="utf-8") as fh:
        fh.writelines(f"b{i:04d} bigtrain bigprobe 6 2\n" for i in range(6))
    return queries


def _instruction_cost(binary, data_dir, queries, tag):
    out = os.path.join(FIT_DIR, f"cg_{tag}")
    subprocess.run(
        [
            "valgrind", "--tool=callgrind", "--quiet",
            f"--callgrind-out-file={out}", binary, data_dir, queries,
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=3000,
    )
    with open(out, encoding="utf-8") as fh:
        blob = fh.read()
    totals = re.findall(r"^summary:\s+(\d+)", blob, re.MULTILINE) or re.findall(
        r"^totals:\s+(\d+)", blob, re.MULTILINE
    )
    assert totals, "callgrind produced no instruction total"
    return int(totals[-1])


@pytest.fixture(scope="session")
def budget_workload(tmp_path_factory):
    root = str(tmp_path_factory.mktemp("budget"))
    queries = _budget_workload(root)
    return root, queries


@pytest.fixture(scope="session")
def rescan_reference(tmp_path_factory):
    """Compile the planted per-candidate rescan used to prove the budget binds."""
    source = os.path.join(REFERENCE_DIR, "rescan_surrogates.cpp")
    if not os.path.isfile(source):
        source = os.path.join(TESTS_DIR, "references", "rescan_surrogates.cpp")
    target = str(tmp_path_factory.mktemp("rescan") / "rescan")
    subprocess.run(
        ["g++", "-std=c++17", "-O2", "-w", "-o", target, source],
        check=True,
        timeout=600,
    )
    return target


def test_fit_stays_within_the_instruction_budget():
    """The fitted model must reach the advertised report within the published budget."""
    assert FIT_OK, COMPILE.stderr[-2000:]


def test_callgrind_budget(budget_workload):
    """Measured cost on the fixed workload stays under the published ceiling."""
    data_dir, queries = budget_workload
    measured = _instruction_cost(BINARY, data_dir, queries, "candidate")
    assert measured <= BUDGET_IR, (
        f"the fit used {measured} instruction reads, over the {BUDGET_IR} ceiling"
    )


def test_rescan_reference_is_correct_but_over_budget(budget_workload, rescan_reference):
    """A per-candidate rescan is correct yet too costly, so the budget really binds."""
    data_dir, queries = budget_workload
    mine = _run(data_dir, queries)
    theirs = subprocess.run(
        [rescan_reference, data_dir, queries],
        capture_output=True,
        text=True,
        check=True,
        timeout=3000,
    )
    other = [ln for ln in theirs.stdout.split("\n") if ln.strip() != ""]
    assert other == mine, "the planted rescan reference is not correctness-equivalent"
    measured = _instruction_cost(rescan_reference, data_dir, queries, "rescan")
    assert measured > BUDGET_IR, (
        f"the planted rescan came in at {measured}, within the {BUDGET_IR} ceiling; "
        "the budget no longer separates a swept search from a per-candidate rescan"
    )
