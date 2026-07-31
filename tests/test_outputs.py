import collections
import os
import tempfile

import metamorphic
import pytest
from build_graph import write
from conftest import (
    HIDDEN_FAMILIES,
    REQUIRED_COLUMNS,
    VISIBLE_GRAPH,
    hidden_graph,
    normalize_rows,
    run_query,
)
from lacp_oracle import compute_reference
from scenarios import SCENARIOS

STATES = ("Detached", "Individual", "Bundled", "Down")
NONE = "NONE"
GROUPED = ("Bundled", "Down")

_TMP = tempfile.mkdtemp(prefix="lacp_derived_")
_BUILT = {}


def _built(name, fabric):
    if name not in _BUILT:
        path = os.path.join(_TMP, name, "lacp_fabric.kuzu")
        write(fabric, path)
        _BUILT[name] = path
    return _BUILT[name]


def _graph_paths():
    paths = {"visible": VISIBLE_GRAPH}
    for family in HIDDEN_FAMILIES:
        paths[family] = hidden_graph(family)
    return paths


def _anchor_ports(reference):
    by_state = collections.defaultdict(list)
    for row in sorted(reference):
        by_state[row[2]].append(row)
    picked = []
    for state in STATES:
        picked.extend(by_state[state][:2])
    return picked


def test_required_columns_present(answer_visible_raw):
    """The answer returns the four contracted columns."""
    columns, rows, err = answer_visible_raw
    assert rows is not None, f"answer query failed on the visible graph: {err}"
    missing = set(REQUIRED_COLUMNS) - set(columns)
    assert not missing, f"answer is missing columns: {missing}"


def test_answer_matches_oracle_on_visible(answer_visible_normalized, visible_reference):
    """The answer reproduces the oracle's row set on the committed fabric."""
    assert answer_visible_normalized == visible_reference


@pytest.mark.parametrize("state", STATES)
def test_visible_state_population(answer_visible_normalized, visible_reference, state):
    """Each aggregation state is populated exactly as the oracle says."""
    got = {r for r in answer_visible_normalized if r[2] == state}
    want = {r for r in visible_reference if r[2] == state}
    assert got == want


@pytest.mark.parametrize("index", range(8))
def test_visible_anchor_row(answer_visible_normalized, visible_reference, index):
    """A sampled port across all four states carries its exact oracle row."""
    anchors = _anchor_ports(visible_reference)
    row = anchors[index]
    assert row in answer_visible_normalized


@pytest.mark.parametrize("index", range(8))
def test_visible_anchor_has_no_rival_row(
    answer_visible_normalized, visible_reference, index
):
    """A sampled port carries no second row under any other state or lag_id."""
    anchors = _anchor_ports(visible_reference)
    row = anchors[index]
    rivals = {
        r
        for r in answer_visible_normalized
        if (r[0], r[1]) == (row[0], row[1]) and r != row
    }
    assert not rivals, f"port {row[1]} also reported as {rivals}"


@pytest.mark.parametrize("family", HIDDEN_FAMILIES)
def test_answer_matches_oracle_on_hidden(
    answer_hidden_normalized, hidden_references, family
):
    """The answer generalizes to a fabric it has never seen."""
    assert answer_hidden_normalized[family] == hidden_references[family]


@pytest.mark.parametrize("family", HIDDEN_FAMILIES)
@pytest.mark.parametrize("state", STATES)
def test_hidden_state_population(
    answer_hidden_normalized, hidden_references, family, state
):
    """Each state is populated correctly on each hidden fabric."""
    got = {r for r in answer_hidden_normalized[family] if r[2] == state}
    want = {r for r in hidden_references[family] if r[2] == state}
    assert got == want


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_scenario_contract(answer_text, name):
    """The answer reproduces a hand-worked fabric isolating one rule."""
    fabric, expected = SCENARIOS[name]()
    path = _built("scenario_" + name, fabric)
    columns, rows, err = run_query(answer_text, path)
    assert rows is not None, f"answer failed on scenario {name}: {err}"
    assert normalize_rows(columns, rows) == expected


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_scenario_oracle_agrees_with_hand_worked_rows(name):
    """The independent oracle reproduces rows worked out by hand from the rules."""
    fabric, expected = SCENARIOS[name]()
    path = _built("scenario_" + name, fabric)
    assert compute_reference(path) == expected


@pytest.mark.parametrize("graph", sorted(_graph_paths()))
def test_reference_query_agrees_with_oracle(reference_text, graph):
    """The shipped reference query and the oracle agree on every fabric."""
    path = _graph_paths()[graph]
    columns, rows, err = run_query(reference_text, path)
    assert rows is not None, f"reference query failed on {graph}: {err}"
    assert normalize_rows(columns, rows) == compute_reference(path)


@pytest.mark.parametrize("graph", sorted(_graph_paths()))
def test_one_row_per_port(answer_text, graph):
    """Every port appears exactly once, whatever its state."""
    path = _graph_paths()[graph]
    columns, rows, err = run_query(answer_text, path)
    assert rows is not None, f"answer failed on {graph}: {err}"
    normalized = normalize_rows(columns, rows)
    keys = [(r[0], r[1]) for r in normalized]
    assert len(keys) == len(set(keys)), "a port is reported more than once"
    assert len(normalized) == len(compute_reference(path))


@pytest.mark.parametrize("graph", sorted(_graph_paths()))
def test_state_enum_is_total(answer_text, graph):
    """No port is reported under a state outside the contracted enum."""
    path = _graph_paths()[graph]
    columns, rows, err = run_query(answer_text, path)
    assert rows is not None, f"answer failed on {graph}: {err}"
    seen = {r[2] for r in normalize_rows(columns, rows)}
    assert seen <= set(STATES), f"unexpected states: {seen - set(STATES)}"


@pytest.mark.parametrize("graph", sorted(_graph_paths()))
def test_lag_id_discipline(answer_text, graph):
    """Grouped ports carry a group identifier and ungrouped ports carry NONE."""
    path = _graph_paths()[graph]
    columns, rows, err = run_query(answer_text, path)
    assert rows is not None, f"answer failed on {graph}: {err}"
    for switch, port, state, lag_id in normalize_rows(columns, rows):
        if state in GROUPED:
            assert lag_id != NONE and ":" in lag_id, (switch, port, state, lag_id)
        else:
            assert lag_id == NONE, (switch, port, state, lag_id)


@pytest.mark.parametrize(
    "baseline",
    [
        "naive_trust_advertised_partner",
        "naive_group_by_actor_key_only",
        "naive_ignore_minlinks",
    ],
)
def test_baseline_diverges_on_visible(request, visible_reference, baseline):
    """A named wrong reading of the rules is separated on the committed fabric."""
    text = request.getfixturevalue(baseline + "_text")
    columns, rows, err = run_query(text, VISIBLE_GRAPH)
    assert rows is not None, f"baseline {baseline} failed to run: {err}"
    assert normalize_rows(columns, rows) != visible_reference


@pytest.mark.parametrize(
    "baseline",
    [
        "naive_trust_advertised_partner",
        "naive_group_by_actor_key_only",
        "naive_ignore_minlinks",
    ],
)
@pytest.mark.parametrize("family", HIDDEN_FAMILIES)
def test_baseline_diverges_on_hidden(request, hidden_references, baseline, family):
    """A named wrong reading is separated on unseen fabrics too."""
    text = request.getfixturevalue(baseline + "_text")
    columns, rows, err = run_query(text, hidden_graph(family))
    assert rows is not None, f"baseline {baseline} failed to run: {err}"
    assert normalize_rows(columns, rows) != hidden_references[family]


def test_literal_list_matches_visible(literal_list_text, visible_reference):
    """The hardcoded row list is indistinguishable on the committed fabric."""
    columns, rows, err = run_query(literal_list_text, VISIBLE_GRAPH)
    assert rows is not None, f"literal_list failed to run: {err}"
    assert normalize_rows(columns, rows) == visible_reference


@pytest.mark.parametrize("family", HIDDEN_FAMILIES)
def test_literal_list_diverges_on_hidden(literal_list_text, hidden_references, family):
    """The hardcoded row list is separated by every unseen fabric."""
    columns, rows, err = run_query(literal_list_text, hidden_graph(family))
    assert rows is not None, f"literal_list failed to run: {err}"
    assert normalize_rows(columns, rows) != hidden_references[family]


def test_metamorphic_link_direction_swap(answer_text):
    """Storing every cable in the opposite direction changes no row."""
    base = _built("mm_base", metamorphic.base_fabric())
    swapped = _built("mm_swap", metamorphic.link_direction_swap())
    columns, rows, err = run_query(answer_text, swapped)
    assert rows is not None, f"answer failed on the swapped fabric: {err}"
    assert normalize_rows(columns, rows) == compute_reference(base)


def test_metamorphic_key_bijection(answer_text):
    """Remapping every key injectively leaves each port's state unchanged."""
    base = _built("mm_base", metamorphic.base_fabric())
    remapped = _built("mm_keys", metamorphic.key_bijection())
    columns, rows, err = run_query(answer_text, remapped)
    assert rows is not None, f"answer failed on the remapped fabric: {err}"
    got = normalize_rows(columns, rows)
    assert got == compute_reference(remapped)
    states = collections.Counter((r[0], r[1], r[2]) for r in got)
    base_states = collections.Counter(
        (r[0], r[1], r[2]) for r in compute_reference(base)
    )
    assert states == base_states


def test_metamorphic_dead_link_addition(answer_text):
    """Adding a cabled pair that is administratively down changes no row."""
    base = _built("mm_base", metamorphic.base_fabric())
    fabric, added = metamorphic.dead_link_addition()
    path = _built("mm_dead", fabric)
    columns, rows, err = run_query(answer_text, path)
    assert rows is not None, f"answer failed on the extended fabric: {err}"
    got = normalize_rows(columns, rows)
    names = {p["name"] for p in added}
    assert {r for r in got if r[1] not in names} == compute_reference(base)
    assert all(r[2] == "Detached" for r in got if r[1] in names)


def test_metamorphic_nonaggregatable_pair_addition(answer_text):
    """Adding a cabled pair that may not aggregate changes no existing row."""
    base = _built("mm_base", metamorphic.base_fabric())
    fabric, added = metamorphic.nonaggregatable_pair_addition()
    path = _built("mm_nonagg", fabric)
    columns, rows, err = run_query(answer_text, path)
    assert rows is not None, f"answer failed on the extended fabric: {err}"
    got = normalize_rows(columns, rows)
    names = {p["name"] for p in added}
    assert {r for r in got if r[1] not in names} == compute_reference(base)
    assert all(r[2] == "Individual" for r in got if r[1] in names)
