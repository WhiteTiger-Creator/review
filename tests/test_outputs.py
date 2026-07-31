import os

import pytest
from conftest import (
    ANSWER_PATH,
    HIDDEN_GRAPH,
    REQUIRED_COLUMNS,
    VISIBLE_GRAPH,
    normalize_rows,
    run_query,
)

UNSYNCHRONIZED = "16"
NO_PEER = "NONE"

ALL_CLIENTS = [
    "all-disjoint",
    "all-unreachable",
    "all-unsynchronized",
    "clean-agreement",
    "dispersion-tie-name",
    "eligibility-filter",
    "fleet-00",
    "fleet-01",
    "fleet-02",
    "fleet-03",
    "fleet-04",
    "fleet-05",
    "fleet-06",
    "fleet-07",
    "fleet-08",
    "fleet-09",
    "fleet-10",
    "lowest-stratum-outlier",
    "majority-wider",
    "nested-offsets",
    "one-out-of-four",
    "overlap-not-offset",
    "single-eligible",
    "stratum-tie-dispersion",
    "tolerated-outlier",
    "two-of-three",
    "zero-width",
]

# Each named scenario's certified row on the committed visible graph.
EXPECTED_ANCHOR_ROWS = [
    ("all-disjoint", "16", "NONE", "0", "3"),
    ("all-unreachable", "16", "NONE", "0", "0"),
    ("all-unsynchronized", "16", "NONE", "0", "0"),
    ("clean-agreement", "3", "stratum04.pdx.example.net", "3", "0"),
    ("dispersion-tie-name", "3", "pool03.bcn.example.net", "3", "0"),
    ("eligibility-filter", "3", "sync04.atl.example.net", "2", "0"),
    ("lowest-stratum-outlier", "5", "tick04.ams.example.net", "2", "1"),
    ("majority-wider", "3", "chrony03.jfk.example.net", "4", "1"),
    ("nested-offsets", "4", "ntp00.gru.example.net", "3", "0"),
    ("one-out-of-four", "3", "stratum01.icn.example.net", "3", "1"),
    ("overlap-not-offset", "3", "chrony04.syd.example.net", "3", "1"),
    ("single-eligible", "5", "chrony01.bcn.example.net", "1", "0"),
    ("stratum-tie-dispersion", "4", "tick00.hkg.example.net", "3", "0"),
    ("tolerated-outlier", "3", "clock03.jfk.example.net", "2", "1"),
    ("two-of-three", "3", "refclk01.yyz.example.net", "2", "1"),
    ("zero-width", "3", "sync04.ams.example.net", "3", "0"),
]

# Rows a disclosed shortcut emits on the visible graph but the full rule set
# forbids. Each witnesses that the corresponding rule is load-bearing.
OVERLAP_EXTRA = ("overlap-not-offset", "3", "chrony04.syd.example.net", "4", "0")
F_ZERO_EXTRA = ("lowest-stratum-outlier", "16", "NONE", "0", "3")
FIXED_MAJORITY_EXTRA = ("majority-wider", "3", "chrony03.jfk.example.net", "5", "0")
ALL_CANDIDATES_EXTRA = ("eligibility-filter", "2", "time02.bcn.example.net", "4", "0")
DISPERSION_PEER_EXTRA = ("clean-agreement", "5", "ntp04.lhr.example.net", "3", "0")

# Rows a shortcut emits that a correct answer must not contain.
SHORTCUT_ROWS_ABSENT = [
    OVERLAP_EXTRA,
    ("one-out-of-four", "3", "stratum01.icn.example.net", "4", "0"),
    F_ZERO_EXTRA,
    ("majority-wider", "16", "NONE", "0", "5"),
    FIXED_MAJORITY_EXTRA,
    ALL_CANDIDATES_EXTRA,
    DISPERSION_PEER_EXTRA,
    ("stratum-tie-dispersion", "5", "tock01.nrt.example.net", "3", "0"),
]


def _probe_count(query):
    columns, rows, err = run_query(query, VISIBLE_GRAPH)
    assert rows is not None, err
    (row,) = rows
    return int(row[columns.index("n")])


# ---- answer file basics ----


def test_answer_file_exists():
    """The agent wrote a query to /app/answer.cypher."""
    assert os.path.exists(ANSWER_PATH)


def test_answer_file_not_empty(answer_text):
    """The submitted answer file is not blank or whitespace only."""
    assert answer_text.strip() != ""


def test_answer_executes_on_visible_graph(answer_visible_raw):
    """The submitted query runs without error against the committed visible graph."""
    _, rows, err = answer_visible_raw
    assert rows is not None, f"query execution failed: {err}"


def test_answer_returns_exact_column_set(answer_visible_raw):
    """The submitted query returns exactly the five requested output columns."""
    columns, rows, err = answer_visible_raw
    assert rows is not None, err
    assert set(columns) == set(REQUIRED_COLUMNS)


def test_answer_returns_at_least_one_row(answer_visible_normalized):
    """The submitted query produces a non-empty result-set on the visible graph."""
    assert len(answer_visible_normalized) > 0


def test_answer_reports_every_client_exactly_once(answer_visible_normalized):
    """The submitted query returns exactly one certification row per client."""
    names = [row[0] for row in answer_visible_normalized]
    assert sorted(names) == sorted(ALL_CLIENTS)


def test_answer_counts_are_integers(answer_visible_normalized):
    """Every stratum, truechimer and falseticker value returned is an integer."""
    for _, stratum, _, truechimers, falsetickers in answer_visible_normalized:
        assert stratum.lstrip("-").isdigit()
        assert truechimers.isdigit()
        assert falsetickers.isdigit()


def test_answer_system_peer_is_never_blank(answer_visible_normalized):
    """No row carries an empty or unbound system_peer instead of a name or NONE."""
    for _, _, peer, _, _ in answer_visible_normalized:
        assert peer != ""


# ---- full set equality on the visible graph ----


def test_visible_result_set_matches_reference_exactly(
    answer_visible_normalized, visible_reference
):
    """The submitted query's result-set equals the independently recomputed answer."""
    assert answer_visible_normalized == visible_reference


def test_visible_result_has_no_extra_rows(answer_visible_normalized, visible_reference):
    """The submitted query returns no row absent from the recomputed result-set."""
    assert answer_visible_normalized - visible_reference == set()


def test_visible_result_is_missing_no_rows(
    answer_visible_normalized, visible_reference
):
    """The submitted query omits no row present in the recomputed result-set."""
    assert visible_reference - answer_visible_normalized == set()


def test_visible_result_row_count_matches_reference(
    answer_visible_normalized, visible_reference
):
    """The submitted query returns the same number of rows as the recomputed answer."""
    assert len(answer_visible_normalized) == len(visible_reference)


@pytest.mark.parametrize("expected_row", EXPECTED_ANCHOR_ROWS)
def test_expected_anchor_row_present(answer_visible_normalized, expected_row):
    """A named scenario's certified stratum, peer and two counts is present."""
    assert expected_row in answer_visible_normalized


@pytest.mark.parametrize("client_name", ALL_CLIENTS)
def test_each_client_row_matches_reference(
    answer_visible_normalized, visible_reference, client_name
):
    """For each client, the submitted certification row equals the recomputed row."""
    answer_row = {row for row in answer_visible_normalized if row[0] == client_name}
    reference_row = {row for row in visible_reference if row[0] == client_name}
    assert answer_row == reference_row


@pytest.mark.parametrize("wrong_row", SHORTCUT_ROWS_ABSENT)
def test_shortcut_row_absent(answer_visible_normalized, wrong_row):
    """A row a shortcut policy emits but the full rule set forbids is absent."""
    assert wrong_row not in answer_visible_normalized


# ---- reference query cross-check against the independent oracle ----


def test_reference_cypher_matches_oracle_on_visible_graph(
    reference_visible_normalized, visible_reference
):
    """The committed reference query reproduces the independently recomputed answer."""
    assert reference_visible_normalized == visible_reference


def test_reference_cypher_matches_oracle_on_hidden_graph(
    reference_hidden_normalized, hidden_reference
):
    """The reference query reproduces the recomputed answer on the hidden graph."""
    assert reference_hidden_normalized == hidden_reference


# ---- disclosed shortcuts are each load-bearing ----


def test_overlap_shortcut_diverges(naive_overlap_text, visible_reference):
    """Counting a candidate whose interval merely overlaps the intersection,
    rather than whose offset lies inside it, over-counts a truechimer."""
    columns, rows, err = run_query(naive_overlap_text, VISIBLE_GRAPH)
    assert rows is not None, err
    naive_rows = normalize_rows(columns, rows)
    assert naive_rows != visible_reference
    assert OVERLAP_EXTRA in naive_rows - visible_reference


def test_f_zero_shortcut_diverges(naive_f_zero_text, visible_reference):
    """Refusing to tolerate any falseticker leaves a client that needs one
    dropped outlier wrongly unsynchronized."""
    columns, rows, err = run_query(naive_f_zero_text, VISIBLE_GRAPH)
    assert rows is not None, err
    naive_rows = normalize_rows(columns, rows)
    assert naive_rows != visible_reference
    assert F_ZERO_EXTRA in naive_rows - visible_reference


def test_fixed_majority_shortcut_diverges(naive_fixed_majority_text, visible_reference):
    """Using a fixed strict-majority region instead of the tolerated
    intersection admits an offset the tighter intersection excludes."""
    columns, rows, err = run_query(naive_fixed_majority_text, VISIBLE_GRAPH)
    assert rows is not None, err
    naive_rows = normalize_rows(columns, rows)
    assert naive_rows != visible_reference
    assert FIXED_MAJORITY_EXTRA in naive_rows - visible_reference


def test_all_candidates_shortcut_diverges(naive_all_candidates_text, visible_reference):
    """Admitting ineligible servers to the selection changes at least one row."""
    columns, rows, err = run_query(naive_all_candidates_text, VISIBLE_GRAPH)
    assert rows is not None, err
    naive_rows = normalize_rows(columns, rows)
    assert naive_rows != visible_reference
    assert ALL_CANDIDATES_EXTRA in naive_rows - visible_reference


def test_dispersion_peer_shortcut_diverges(
    naive_dispersion_peer_text, visible_reference
):
    """Ordering the peer ladder by dispersion before stratum reseats the peer."""
    columns, rows, err = run_query(naive_dispersion_peer_text, VISIBLE_GRAPH)
    assert rows is not None, err
    naive_rows = normalize_rows(columns, rows)
    assert naive_rows != visible_reference
    assert DISPERSION_PEER_EXTRA in naive_rows - visible_reference


@pytest.mark.parametrize(
    "naive_fixture",
    [
        "naive_overlap_text",
        "naive_f_zero_text",
        "naive_fixed_majority_text",
        "naive_all_candidates_text",
        "naive_dispersion_peer_text",
    ],
)
def test_shortcut_is_load_bearing(request, naive_fixture, visible_reference):
    """Each disclosed shortcut moves at least one row away from the reference."""
    text = request.getfixturevalue(naive_fixture)
    columns, rows, err = run_query(text, VISIBLE_GRAPH)
    assert rows is not None, err
    naive_rows = normalize_rows(columns, rows)
    assert len(naive_rows - visible_reference) > 0


# ---- intersection-algorithm coupling ----


def test_overlap_without_offset_is_a_falseticker(visible_reference):
    """A wide interval overlapping the agreed region, whose offset lies outside
    it, is certified a falseticker, not a truechimer."""
    (row,) = [r for r in visible_reference if r[0] == "overlap-not-offset"]
    assert row[3] == "3" and row[4] == "1"


def test_a_tolerated_outlier_still_synchronizes(visible_reference):
    """A client with one disagreeing server still certifies against the rest."""
    (row,) = [r for r in visible_reference if r[0] == "tolerated-outlier"]
    assert row[2] != NO_PEER and row[3] == "2" and row[4] == "1"


def test_wider_majority_would_admit_an_extra_offset(visible_reference):
    """The tolerated intersection is tighter than a strict-majority region: the
    stray offset is excluded, leaving one falseticker."""
    (row,) = [r for r in visible_reference if r[0] == "majority-wider"]
    assert row[3] == "4" and row[4] == "1"


def test_fully_disjoint_client_is_unsynchronized(visible_reference):
    """A client whose measurements never agree is left unsynchronized."""
    (row,) = [r for r in visible_reference if r[0] == "all-disjoint"]
    assert row[1] == UNSYNCHRONIZED and row[2] == NO_PEER and row[3] == "0"


# ---- anti-hardcode ----


def test_literal_list_matches_reference_on_visible_graph(
    literal_list_text, visible_reference
):
    """A hardcoded row list reproduces the answer on the graph it was copied from."""
    columns, rows, err = run_query(literal_list_text, VISIBLE_GRAPH)
    assert rows is not None, err
    assert normalize_rows(columns, rows) == visible_reference


def test_literal_list_diverges_from_reference_on_hidden_graph(
    literal_list_text, hidden_reference
):
    """The hardcoded row list fails to reproduce the answer on the hidden-seed graph."""
    columns, rows, err = run_query(literal_list_text, HIDDEN_GRAPH)
    assert rows is not None, err
    assert normalize_rows(columns, rows) != hidden_reference


# ---- generalization to the hidden graph ----


def test_answer_executes_on_hidden_graph(answer_hidden_raw):
    """The submitted query also runs without error against the hidden-seed graph."""
    _, rows, err = answer_hidden_raw
    assert rows is not None, f"query execution failed on the hidden graph: {err}"


def test_hidden_result_returns_exact_column_set(answer_hidden_raw):
    """The submitted query returns exactly the five columns on the hidden graph."""
    columns, rows, err = answer_hidden_raw
    assert rows is not None, err
    assert set(columns) == set(REQUIRED_COLUMNS)


def test_hidden_result_set_matches_reference_exactly(
    answer_hidden_normalized, hidden_reference
):
    """The submitted query generalizes: its result-set equals the hidden-graph answer."""
    assert answer_hidden_normalized == hidden_reference


def test_hidden_result_row_count_matches_reference(
    answer_hidden_normalized, hidden_reference
):
    """The submitted query returns the same row count as the hidden reference answer."""
    assert len(answer_hidden_normalized) == len(hidden_reference)


@pytest.mark.parametrize("client_name", ALL_CLIENTS)
def test_each_hidden_client_row_matches_reference(
    answer_hidden_normalized, hidden_reference, client_name
):
    """For each client on the hidden graph, the submitted row equals the recomputed row."""
    answer_row = {row for row in answer_hidden_normalized if row[0] == client_name}
    reference_row = {row for row in hidden_reference if row[0] == client_name}
    assert answer_row == reference_row


def test_hidden_reference_result_is_nonempty(hidden_reference):
    """The hidden-seed graph's independently recomputed answer is non-trivial."""
    assert len(hidden_reference) > 0


def test_hidden_reference_differs_from_visible_reference(
    hidden_reference, visible_reference
):
    """The hidden-seed graph is a genuinely different instance, not a copy."""
    assert hidden_reference != visible_reference


def test_hidden_graph_is_a_separate_database_from_the_visible_graph():
    """The hidden-seed graph is stored as its own database directory."""
    assert os.path.abspath(HIDDEN_GRAPH) != os.path.abspath(VISIBLE_GRAPH)
    assert os.path.isdir(HIDDEN_GRAPH)
    assert os.path.isdir(VISIBLE_GRAPH)


def test_hidden_server_names_are_disjoint_from_visible():
    """No server identity is shared between the visible and hidden graphs."""

    def servers(graph):
        columns, rows, err = run_query("MATCH (s:Server) RETURN s.name AS name", graph)
        assert rows is not None, err
        return {row[columns.index("name")] for row in rows}

    assert servers(VISIBLE_GRAPH) & servers(HIDDEN_GRAPH) == set()


# ---- structural invariants of the shipped visible graph ----


def test_an_unreachable_server_exists_in_the_visible_graph():
    """Some candidate is measured against an unreachable server."""
    assert (
        _probe_count(
            "MATCH (k:Candidate)-[:FROM_SERVER]->(s:Server) "
            "WHERE NOT s.reachable RETURN count(k) AS n"
        )
        > 0
    )


def test_an_unsynchronized_server_exists_in_the_visible_graph():
    """Some candidate is measured against a server whose own stratum is 16."""
    assert (
        _probe_count(
            "MATCH (k:Candidate)-[:FROM_SERVER]->(s:Server) "
            "WHERE s.stratum = 16 RETURN count(k) AS n"
        )
        > 0
    )


def test_a_zero_width_interval_exists_in_the_visible_graph():
    """Some candidate's correctness interval is a single position."""
    assert (
        _probe_count("MATCH (k:Candidate) WHERE k.lo = k.hi RETURN count(k) AS n") > 0
    )


def test_every_offset_lies_within_its_interval():
    """Each candidate's measured offset falls inside its own correctness interval."""
    assert (
        _probe_count(
            "MATCH (k:Candidate) WHERE k.offset < k.lo OR k.offset > k.hi "
            "RETURN count(k) AS n"
        )
        == 0
    )


def test_a_server_backs_more_than_one_client_in_the_visible_graph():
    """Some server is measured by candidates belonging to several clients."""
    assert (
        _probe_count(
            "MATCH (s:Server) "
            "WHERE COUNT { MATCH (k:Candidate)-[:FROM_SERVER]->(s), "
            "(k)-[:OF]->(c:Client) } > 1 RETURN count(s) AS n"
        )
        > 0
    )


def test_visible_answer_contains_a_synchronized_client(visible_reference):
    """At least one client is certified against a real system peer."""
    assert any(peer != NO_PEER for _, _, peer, _, _ in visible_reference)


def test_visible_answer_contains_an_unsynchronized_client(visible_reference):
    """At least one client is certified unsynchronized."""
    assert any(peer == NO_PEER for _, _, peer, _, _ in visible_reference)


def test_visible_answer_contains_a_falseticker(visible_reference):
    """At least one eligible candidate is certified a falseticker."""
    assert any(int(falsetickers) > 0 for *_, falsetickers in visible_reference)


def test_visible_answer_contains_a_truechimer(visible_reference):
    """At least one eligible candidate is certified a truechimer."""
    assert any(int(row[3]) > 0 for row in visible_reference)


def test_unsynchronized_clients_report_stratum_sixteen(visible_reference):
    """Every client without a system peer reports stratum 16 and no truechimer."""
    for _, stratum, peer, truechimers, _ in visible_reference:
        if peer == NO_PEER:
            assert stratum == UNSYNCHRONIZED
            assert truechimers == "0"


def test_synchronized_clients_have_a_truechimer(visible_reference):
    """Every client with a system peer has at least one truechimer."""
    for _, _, peer, truechimers, _ in visible_reference:
        if peer != NO_PEER:
            assert int(truechimers) > 0


def test_visible_reference_result_has_meaningful_size(visible_reference):
    """The recomputed answer is large enough for set equality to be a real bar."""
    assert len(visible_reference) >= 20
