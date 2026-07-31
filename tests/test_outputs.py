import os
import sys

import build_graph as bg
import pytest
import query_utils as qu
from placement_oracle import Cluster

HERE = os.path.dirname(os.path.abspath(__file__))
APP = "/app"
ANSWER = os.path.join(APP, "answer.sparql")
VIS_GRAPH = os.path.join(APP, "graph", "cluster.nt")
FIX = os.path.join(HERE, "fixtures")
HID_GRAPH = os.path.join(FIX, "hidden_graph", "cluster.nt")

VISIBLE_SEED = "k8s-placement-visible-01"
HIDDEN_SEED = "k8s-placement-hidden-77"

NS = bg.NS

_vis_store = qu.load_store(VIS_GRAPH)
_hid_store = qu.load_store(HID_GRAPH)
_vis = Cluster(_vis_store)
_hid = Cluster(_hid_store)
_vis_model = bg.build(VISIBLE_SEED)
_hid_model = bg.build(HIDDEN_SEED)

ORACLE_VIS = _vis.rows()
ORACLE_HID = _hid.rows()

REF = qu.read_fixture("reference.rq")
BASELINES = {
    "naive_any_taint_tolerated": (
        "naive_any_taint_tolerated.rq",
        "naive_any_taint_rows",
    ),
    "naive_ignore_eviction": (
        "naive_ignore_eviction.rq",
        "naive_ignore_eviction_rows",
    ),
    "naive_antiaffinity_same_node_only": (
        "naive_antiaffinity_same_node_only.rq",
        "naive_same_node_only_rows",
    ),
}

REF_VIS = qu.result_set(_vis_store, REF)
REF_HID = qu.result_set(_hid_store, REF)

BASE_VIS = {}
BASE_HID = {}
for _name, (_file, _method) in BASELINES.items():
    _text = qu.read_fixture(_file)
    BASE_VIS[_name] = qu.result_set(_vis_store, _text)
    BASE_HID[_name] = qu.result_set(_hid_store, _text)

SCENARIOS = sorted(_vis_model["reserved_pending"])
_agent_cache = {}


def _answer_text():
    return qu.read_text(ANSWER)


def _agent_rows(key, store):
    if key not in _agent_cache:
        _agent_cache[key] = qu.result_set(store, _answer_text())
    return _agent_cache[key]


def agent_vis():
    return _agent_rows("visible", _vis_store)


def agent_hid():
    return _agent_rows("hidden", _hid_store)


def _row_for(rows, pod):
    for row in rows:
        if row[0] == pod:
            return row
    return None


def _scenario_pod(model, name):
    return model["reserved_pending"][name]


def _literal_list_query(rows):
    lines = [f"    (<{pod}> {sched} {count})" for pod, sched, count in sorted(rows)]
    return (
        "SELECT ?pod ?schedulable ?feasible_node_count WHERE {\n"
        "  VALUES (?pod ?schedulable ?feasible_node_count) {\n"
        + "\n".join(lines)
        + "\n  }\n}\n"
    )


LITERAL_LIST = _literal_list_query(ORACLE_VIS)


# Each addition below is a graph edit the disclosed rules prove cannot move a
# single verdict, so both the oracle and any contract-complete query must
# return exactly the rows they returned before the edit.
def _triples_for_evicted_occupant(model):
    pod = NS + "mm_pod_evicted_occupant"
    return (
        f"<{pod}> <{bg.RDF_TYPE}> <{NS}Pod> .\n"
        + f'<{pod}> <{NS}pending> "false"^^<{bg.XSD_BOOL}> .\n'
        + "<{}> <{}placedOn> <{}> .\n".format(pod, NS, model["reserved_nodes"]["maint"])
        + "<{}> <{}hasPodLabel> <{}> .\n".format(
            pod, NS, model["labels"][("app", "batch")]
        )
    )


def _triples_for_saturated_domain(model):
    pod = NS + "mm_pod_saturating"
    return (
        f"<{pod}> <{bg.RDF_TYPE}> <{NS}Pod> .\n"
        + f'<{pod}> <{NS}pending> "false"^^<{bg.XSD_BOOL}> .\n'
        + "<{}> <{}placedOn> <{}> .\n".format(
            pod, NS, model["reserved_nodes"]["conflict_host"]
        )
        + "<{}> <{}hasPodLabel> <{}> .\n".format(
            pod, NS, model["labels"][("app", "api")]
        )
    )


def _triples_for_unlabelled_pod(model):
    pod = NS + "mm_pod_unlabelled"
    return (
        f"<{pod}> <{bg.RDF_TYPE}> <{NS}Pod> .\n"
        + f'<{pod}> <{NS}pending> "false"^^<{bg.XSD_BOOL}> .\n'
        + "<{}> <{}placedOn> <{}> .\n".format(
            pod, NS, model["reserved_nodes"]["clean_2"]
        )
    )


def _triples_for_prefer_taint(model):
    taint = NS + "mm_taint_prefer"
    return (
        f"<{taint}> <{bg.RDF_TYPE}> <{NS}Taint> .\n"
        + f'<{taint}> <{NS}key> "drain" .\n'
        + f'<{taint}> <{NS}value> "soon" .\n'
        + f'<{taint}> <{NS}effect> "PreferNoSchedule" .\n'
        + "<{}> <{}hasTaint> <{}> .\n".format(
            model["reserved_nodes"]["clean_1"], NS, taint
        )
    )


ADDITIONS = {
    "evicted_occupant": _triples_for_evicted_occupant,
    "saturated_domain": _triples_for_saturated_domain,
    "unlabelled_pod": _triples_for_unlabelled_pod,
    "prefer_taint": _triples_for_prefer_taint,
}


def _augmented_text():
    base = qu.read_text(VIS_GRAPH)
    return {k: base + fn(_vis_model) for k, fn in ADDITIONS.items()}


AUGMENTED = _augmented_text()

ZONE_BIJECTION = {
    "zone_a": "zone_w",
    "zone_b": "zone_x",
    "zone_c": "zone_y",
    "zone_d": "zone_z",
}


def _zone_relabelled_text():
    text = qu.read_text(VIS_GRAPH)
    for old, new in ZONE_BIJECTION.items():
        iri = _vis_model["labels"][("zone", old)]
        src = f'<{iri}> <{NS}value> "{old}" .'
        dst = f'<{iri}> <{NS}value> "{new}" .'
        assert src in text
        text = text.replace(src, dst)
    return text


RELABELLED = _zone_relabelled_text()


def _negative_pairs():
    out = []
    for name in sorted(BASELINES):
        for scenario in SCENARIOS:
            pod = _scenario_pod(_vis_model, scenario)
            wrong = _row_for(BASE_VIS[name], pod)
            right = _row_for(ORACLE_VIS, pod)
            if wrong is not None and wrong != right:
                out.append((name, scenario, wrong))
    return out


NEGATIVE_PAIRS = _negative_pairs()
WRONG_VALUE_SCENARIOS = SCENARIOS[:10]


def test_verifier_modules_resolve_from_tests_directory():
    """Graph builder, oracle and query helpers load from the read-only tests tree."""
    loaded = (bg, qu, sys.modules[Cluster.__module__])
    assert all(os.path.dirname(os.path.abspath(m.__file__)) == HERE for m in loaded)


def test_answer_file_exists():
    """The candidate produced a query file at the contract path."""
    assert os.path.exists(ANSWER)


def test_answer_non_empty():
    """The candidate query file is not blank."""
    assert _answer_text().strip()


def test_answer_executes_on_visible_graph():
    """The candidate query executes against the committed graph without error."""
    assert agent_vis() is not None


def test_answer_projects_contract_columns():
    """The candidate query projects exactly the three contract columns in order."""
    variables, _ = qu.run_query(_vis_store, _answer_text())
    assert variables == qu.CONTRACT_COLUMNS


def test_answer_emits_one_row_per_pending_pod_visible():
    """The candidate returns exactly one row for each pending pod on the visible graph."""
    _, rows = qu.run_query(_vis_store, _answer_text())
    assert sorted(r[0] for r in rows) == sorted(_vis.pending)


def test_answer_emits_one_row_per_pending_pod_hidden():
    """The candidate returns exactly one row for each pending pod on the hidden graph."""
    _, rows = qu.run_query(_hid_store, _answer_text())
    assert sorted(r[0] for r in rows) == sorted(_hid.pending)


def test_answer_schedulable_values_are_boolean_visible():
    """Every schedulable cell the candidate emits renders as true or false."""
    assert all(row[1] in ("true", "false") for row in agent_vis())


def test_answer_counts_are_non_negative_visible():
    """Every feasible node count the candidate emits is a non-negative integer."""
    assert all(isinstance(row[2], int) and row[2] >= 0 for row in agent_vis())


def test_answer_schedulable_agrees_with_count_visible():
    """The candidate marks a pod schedulable exactly when its count is above zero."""
    assert all((row[1] == "true") == (row[2] > 0) for row in agent_vis())


def test_answer_rows_are_pending_pods_only_visible():
    """The candidate never emits a row for a pod that is not pending."""
    assert {row[0] for row in agent_vis()} <= _vis.pending


def test_agent_matches_oracle_visible():
    """The candidate result set equals the independent oracle on the visible graph."""
    assert agent_vis() == ORACLE_VIS


def test_agent_matches_oracle_hidden():
    """The candidate result set equals the independent oracle on the hidden graph."""
    assert agent_hid() == ORACLE_HID


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_agent_row_matches_oracle_for_scenario_visible(scenario):
    """The candidate's row for one named placement scenario matches the oracle on the visible graph."""
    pod = _scenario_pod(_vis_model, scenario)
    assert _row_for(agent_vis(), pod) == _row_for(ORACLE_VIS, pod)


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_agent_row_matches_oracle_for_scenario_hidden(scenario):
    """The candidate's row for one named placement scenario matches the oracle on the hidden graph."""
    pod = _scenario_pod(_hid_model, scenario)
    assert _row_for(agent_hid(), pod) == _row_for(ORACLE_HID, pod)


@pytest.mark.parametrize("name,scenario,wrong", NEGATIVE_PAIRS)
def test_agent_rejects_shortcut_row(name, scenario, wrong):
    """The candidate does not emit the row a named shortcut policy produces for this scenario."""
    assert wrong not in agent_vis()


@pytest.mark.parametrize("scenario", WRONG_VALUE_SCENARIOS)
def test_agent_rejects_perturbed_count_for_scenario(scenario):
    """The candidate does not emit the right pod with a count one above the truth."""
    pod = _scenario_pod(_vis_model, scenario)
    right = _row_for(ORACLE_VIS, pod)
    assert (right[0], right[1], right[2] + 1) not in agent_vis()


def test_reference_agrees_with_oracle_visible():
    """The reference query and the independent oracle agree on the visible graph."""
    assert REF_VIS == ORACLE_VIS


def test_reference_agrees_with_oracle_hidden():
    """The reference query and the independent oracle agree on the hidden graph."""
    assert REF_HID == ORACLE_HID


@pytest.mark.parametrize("name", sorted(BASELINES))
def test_baseline_implements_its_named_mistake_visible(name):
    """The baseline fixture reproduces its named wrong policy exactly on the visible graph."""
    method = getattr(_vis, BASELINES[name][1])
    assert BASE_VIS[name] == method()


@pytest.mark.parametrize("name", sorted(BASELINES))
def test_baseline_implements_its_named_mistake_hidden(name):
    """The baseline fixture reproduces its named wrong policy exactly on the hidden graph."""
    method = getattr(_hid, BASELINES[name][1])
    assert BASE_HID[name] == method()


@pytest.mark.parametrize("name", sorted(BASELINES))
def test_baseline_diverges_from_oracle_visible(name):
    """The baseline disagrees with the oracle on the visible graph, so it cannot score."""
    assert BASE_VIS[name] != ORACLE_VIS


@pytest.mark.parametrize("name", sorted(BASELINES))
def test_baseline_diverges_from_oracle_hidden(name):
    """The baseline disagrees with the oracle on the hidden graph, so it cannot score."""
    assert BASE_HID[name] != ORACLE_HID


@pytest.mark.parametrize("name", sorted(BASELINES))
def test_agent_differs_from_baseline_visible(name):
    """The candidate's rows are not the rows of any named wrong baseline."""
    assert agent_vis() != BASE_VIS[name]


def test_literal_list_matches_oracle_on_visible():
    """A query that hardcodes the visible answer rows does match the oracle on the visible graph."""
    assert qu.result_set(_vis_store, LITERAL_LIST) == ORACLE_VIS


def test_literal_list_diverges_from_oracle_on_hidden():
    """The same hardcoded query fails on the hidden graph, so hardcoding cannot score."""
    assert qu.result_set(_hid_store, LITERAL_LIST) != ORACLE_HID


def test_hidden_oracle_disjoint_from_visible():
    """The hidden graph reshuffles identities so it shares no pod row with the visible one."""
    assert not ({r[0] for r in ORACLE_VIS} & {r[0] for r in ORACLE_HID})


@pytest.mark.parametrize("name", sorted(ADDITIONS))
def test_oracle_invariant_under_no_op_edit(name):
    """The oracle returns identical rows after a graph edit the rules prove is inert."""
    assert Cluster(qu.load_store_text(AUGMENTED[name])).rows() == ORACLE_VIS


@pytest.mark.parametrize("name", sorted(ADDITIONS))
def test_agent_invariant_under_no_op_edit(name):
    """The candidate returns identical rows after a graph edit the rules prove is inert."""
    store = qu.load_store_text(AUGMENTED[name])
    assert qu.result_set(store, _answer_text()) == ORACLE_VIS


def test_oracle_invariant_under_topology_value_bijection():
    """Renaming every topology domain value preserves the partition, so the oracle is unchanged."""
    assert Cluster(qu.load_store_text(RELABELLED)).rows() == ORACLE_VIS


def test_agent_invariant_under_topology_value_bijection():
    """The candidate depends on the topology partition, not on the literal domain values."""
    store = qu.load_store_text(RELABELLED)
    assert qu.result_set(store, _answer_text()) == ORACLE_VIS


def test_committed_graph_matches_its_generator():
    """The committed graph is exactly what its recorded seed deterministically produces."""
    assert qu.read_text(VIS_GRAPH) == bg.to_nt(_vis_model["triples"])


def test_hidden_graph_matches_its_generator():
    """The hidden graph is exactly what its own distinct seed deterministically produces."""
    assert qu.read_text(HID_GRAPH) == bg.to_nt(_hid_model["triples"])


def test_graph_node_count():
    """The committed graph holds the expected number of worker nodes."""
    assert len(_vis.nodes) == bg.NODE_TOTAL


def test_graph_pending_count():
    """The committed graph holds the expected number of pending pods."""
    assert len(_vis.pending) == bg.PENDING_TOTAL


def test_graph_placed_count():
    """The committed graph holds the expected number of already-placed pods."""
    assert len(_vis.placed) == bg.PLACED_TOTAL


def test_pending_pods_are_not_placed():
    """No pending pod carries a placement, so occupancy comes only from placed pods."""
    assert not (_vis.pending & set(_vis.placed))


def test_each_node_has_at_most_one_label_per_key():
    """No node carries two labels sharing a key, so each topology domain value is unambiguous."""
    for node in _vis.nodes:
        keys = [_vis.label_kv[x][0] for x in _vis.node_labels.get(node, ())]
        assert len(keys) == len(set(keys))


def test_untolerated_noschedule_node_exists():
    """Some pending pod is excluded from some node purely by an untolerated NoSchedule taint."""
    pod = _scenario_pod(_vis_model, "two_taint_partial")
    node = _vis_model["reserved_nodes"]["two_taint"]
    assert not _vis.admits(pod, node)


def test_prefer_no_schedule_node_never_excludes():
    """A node whose only taint is PreferNoSchedule admits a pod holding no tolerations at all."""
    pod = _scenario_pod(_vis_model, "prefer_only")
    node = _vis_model["reserved_nodes"]["prefer"]
    assert _vis.admits(pod, node)


def test_node_without_topology_key_exists_and_is_excluded():
    """A node carrying no label for the required topology key is excluded from that pod."""
    pod = _scenario_pod(_vis_model, "missing_topokey")
    node = _vis_model["reserved_nodes"]["norack_1"]
    assert _vis.topo_value(node, "rack") is None
    assert not _vis.feasible(pod, node)


def test_cross_node_domain_conflict_exists():
    """A node free of any matching occupant is still excluded through its topology domain."""
    pod = _scenario_pod(_vis_model, "cross_node_domain")
    node = _vis_model["reserved_nodes"]["zoneb_peer"]
    selector = _vis_model["labels"][("app", "api")]
    assert selector not in _vis.pod_labels.get(node, set())
    assert not _vis.feasible(pod, node)


def test_evicted_occupant_exists():
    """Some placed pod fails a NoExecute taint on its own node and is therefore not resident."""
    assert not _vis.resident(_vis_model["reserved_placed"]["partial_evicted"])


def test_evicting_and_resident_occupant_share_one_node():
    """One node hosts both an evicted pod and a resident pod, so residency is per pod."""
    placed = _vis_model["reserved_placed"]
    host = _vis_model["reserved_nodes"]["maint"]
    assert _vis.placed[placed["partial_evicted"]] == host
    assert _vis.placed[placed["wildcard_resident"]] == host
    assert _vis.resident(placed["wildcard_resident"])


def test_noschedule_taint_does_not_evict_its_occupant():
    """A placed pod failing a NoSchedule taint on its node still stays resident."""
    placed = _vis_model["reserved_placed"]["noschedule_stuck"]
    host = _vis.placed[placed]
    assert any(
        _vis.taint_kve[t][2] == "NoSchedule" and not _vis.tolerates(placed, t)
        for t in _vis.node_taints[host]
    )
    assert _vis.resident(placed)


def test_empty_key_wildcard_toleration_is_live():
    """A pod holding the empty-key wildcard toleration is admitted to every node."""
    pod = _scenario_pod(_vis_model, "empty_key_wildcard")
    assert all(_vis.admits(pod, n) for n in _vis.nodes)


def test_empty_effect_toleration_matches_across_effects():
    """A toleration with an empty effect covers a taint whose effect is NoExecute."""
    pod = _scenario_pod(_vis_model, "empty_effect")
    node = _vis_model["reserved_nodes"]["maint"]
    assert _vis.admits(pod, node)


def test_operator_equal_rejects_a_different_value():
    """An Equal toleration does not cover a taint sharing its key but not its value."""
    pod = _scenario_pod(_vis_model, "exists_vs_equal")
    assert not _vis.admits(pod, _vis_model["reserved_nodes"]["ded_ml"])
    assert _vis.admits(pod, _vis_model["reserved_nodes"]["ded_infra"])


def test_operator_exists_accepts_any_value():
    """An Exists toleration covers every taint sharing its key whatever the value."""
    pod = _scenario_pod(_vis_model, "exists_any_value")
    assert _vis.admits(pod, _vis_model["reserved_nodes"]["ded_ml"])
    assert _vis.admits(pod, _vis_model["reserved_nodes"]["ded_infra"])


def test_both_schedulable_verdicts_occur():
    """The committed graph produces both a schedulable and an unschedulable verdict."""
    verdicts = {row[1] for row in ORACLE_VIS}
    assert verdicts == {"true", "false"}


def test_zero_count_pod_still_returns_a_row():
    """A pod feasible on no node at all still appears, with a count of zero."""
    pod = _scenario_pod(_vis_model, "count_zero")
    assert _row_for(ORACLE_VIS, pod) == (pod, "false", 0)


def test_eviction_raises_a_count_the_any_taint_shortcut_lowers():
    """The existential tolerance shortcut wrongly keeps an occupant, losing a genuinely open domain."""
    pod = _scenario_pod(_vis_model, "both_signs")
    node = _vis_model["reserved_nodes"]["clean_1"]
    assert _vis.feasible(pod, node)
    assert not _vis.naive_any_taint_feasible(pod, node)


def test_universal_tolerance_lowers_a_count_the_any_taint_shortcut_raises():
    """The same shortcut wrongly admits a node carrying a second untolerated taint."""
    pod = _scenario_pod(_vis_model, "both_signs")
    node = _vis_model["reserved_nodes"]["two_taint"]
    assert not _vis.feasible(pod, node)
    assert _vis.naive_any_taint_feasible(pod, node)
