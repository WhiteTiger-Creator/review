"""Behavioral checks for the curtailment desk emit/verify contract."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
ENV_ROOT = Path("/app/environment")
DOSSIER = APP / "runtime" / "dossier" / "dossier.json"
TRANSCRIPT = APP / "runtime" / "transcript" / "transcript.json"
CLOSED = APP / "corpora" / "closed_instances.json"
ARM_OMIT = APP / "corpora" / "arm_omit_cases.jsonl"
PERM = APP / "corpora" / "perm_stress.jsonl"
JOURNAL = APP / "runtime" / "journal"
STAMP = JOURNAL / "epoch.stamp"


def fnv1a32(s: str) -> int:
    h = 2166136261
    for b in bytes(s, "utf-8"):
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = bytes(data, "utf-8")
    return hashlib.sha256(data).hexdigest()


def expected_slot(left: int, right: int) -> int:
    return ((left + 3) * (right + 5) + 19) % 97


def expected_boosted(left: int, right: int, depth: int, boost: int) -> int:
    return (expected_slot(left, right) + (depth * 7) + boost) % 97


def expected_gap(gap_a: int, gap_b: int, depth: int) -> int:
    return (gap_a * 3 + gap_b * 5 + depth * 7) % 97


def expected_fragment(graph: str, depth: int) -> str:
    continuity = (fnv1a32(graph) + depth * 13) % 100000
    return f"G:{graph}|D:{depth}|C:N{continuity}"


def expected_seal(payload: str, ctx: str) -> str:
    material = bytes(payload, "utf-8") + b"\x1f" + bytes(ctx, "utf-8")
    return sha256_hex(material)


def expected_payload(iid: str, boosted: int, frag: str) -> str:
    return f"{iid}|{boosted}|{frag}"


def expected_ctx(graph: str, depth: int) -> str:
    return f"{graph}:{depth}"


def slash_ctx(graph: str, depth: int) -> str:
    return f"{graph}/{depth}"


def payload_only_digest(payload: str) -> str:
    return sha256_hex(payload)


def swapped_slot(left: int, right: int) -> int:
    return ((left + 5) * (right + 3) + 19) % 97


def sum_slot(left: int, right: int) -> int:
    return ((left + 3) + (right + 5) + 19) % 97


def equal_additive_slot(left: int, right: int) -> int:
    return ((left + 5) + (right + 3) + 19) % 97


def run_emit_verify() -> None:
    assert ENV_ROOT.exists()
    r1 = subprocess.run(
        [
            "/app/pvsim",
            "emit",
            "--scl",
            "/app/fixtures",
            "--corpora",
            "/app/corpora",
            "--annex",
            "/app/annex/slice_137.txt",
            "--out",
            "/app/runtime/dossier",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r1.returncode == 0, r1.stdout + r1.stderr
    r2 = subprocess.run(
        [
            "/app/pvsim",
            "verify",
            "--fuzz",
            "--dossier",
            "/app/runtime/dossier",
            "--out",
            "/app/runtime/transcript",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r2.returncode == 0, r2.stdout + r2.stderr


@pytest.fixture(scope="module")
def artifacts():
    run_emit_verify()
    dossier = json.loads(DOSSIER.read_text())
    transcript = json.loads(TRANSCRIPT.read_text())
    closed = json.loads(CLOSED.read_text())
    return dossier, transcript, closed


def _row_by_id(dossier, iid: str):
    for r in dossier["dossier_rows"]:
        if r["instance_id"] == iid:
            return r
    return None


def _tr_by_id(transcript, iid: str):
    for r in transcript["instances"]:
        if r["instance_id"] == iid:
            return r
    return None


def _arm_cases():
    return [
        json.loads(line)
        for line in ARM_OMIT.read_text().splitlines()
        if line.strip()
    ]


def _closed_map(closed):
    return {i["instance_id"]: i for i in closed["instances"]}


def _load_shard(name: str):
    path = JOURNAL / name
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_asymmetric_rejects_swapped_offsets(artifacts):
    """Asymmetric pairs must reject swapped (+5,+3) near-miss pairing."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if i["left"] != i["right"]]
    assert len(hits) >= 40
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        want = expected_slot(inst["left"], inst["right"])
        assert row["slot_score"] == want
        assert want != swapped_slot(inst["left"], inst["right"])

def test_asymmetric_rejects_additive_pairing(artifacts):
    """Asymmetric pairs must reject additive a+b+19 near-miss pairing."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if i["left"] != i["right"]]
    for inst in hits[:60]:
        row = _row_by_id(dossier, inst["instance_id"])
        want = expected_slot(inst["left"], inst["right"])
        assert row["slot_score"] == want
        if want != sum_slot(inst["left"], inst["right"]):
            assert row["slot_score"] != sum_slot(inst["left"], inst["right"])

def test_equal_index_pairing_contract(artifacts):
    """Equal-index rows must still follow product pairing."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if i["left"] == i["right"]]
    assert len(hits) >= 5
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["slot_score"] == expected_slot(inst["left"], inst["right"])

def test_high_slot_no_clamp_above_90(artifacts):
    """Slots above 90 must not be clamped or rewritten."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if expected_slot(i["left"], i["right"]) > 90]
    assert len(hits) >= 10
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["slot_score"] == expected_slot(inst["left"], inst["right"])

def test_slot_range_closed_universe(artifacts):
    """Every closed slot_score stays in [0, 96]."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        assert 0 <= row["slot_score"] < 97

def test_unboosted_identity_depth_boost_zero(artifacts):
    """When depth and boost are both zero, boosted_score equals slot_score."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if i["nest_depth"] == 0 and i["boost"] == 0]
    assert len(hits) >= 1
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["slot_score"] == expected_slot(inst["left"], inst["right"])
        assert row["boosted_score"] == row["slot_score"]

def test_left_zero_right_nonzero_pairing(artifacts):
    """left=0 with nonzero right still uses (+3,+5) product pairing."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if i["left"] == 0 and i["right"] != 0]
    assert len(hits) >= 3
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["slot_score"] == expected_slot(0, inst["right"])

def test_right_zero_left_nonzero_pairing(artifacts):
    """right=0 with nonzero left still uses (+3,+5) product pairing."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if i["right"] == 0 and i["left"] != 0]
    assert len(hits) >= 3
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["slot_score"] == expected_slot(inst["left"], 0)

def test_pairing_constant_nineteen_not_seventeen(artifacts):
    """Pairing additive constant must be 19, not a 17 near-miss."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"][:50]:
        row = _row_by_id(dossier, inst["instance_id"])
        near = ((inst["left"] + 3) * (inst["right"] + 5) + 17) % 97
        want = expected_slot(inst["left"], inst["right"])
        assert row["slot_score"] == want
        if near != want:
            assert row["slot_score"] != near

def test_pairing_mod_prime_ninety_seven(artifacts):
    """Pairing residues must wrap under mod 97, not mod 100."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        raw = (inst["left"] + 3) * (inst["right"] + 5) + 19
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["slot_score"] == raw % 97
        if raw % 100 != raw % 97:
            assert row["slot_score"] != raw % 100

def test_boost_rejects_doubled_term(artifacts):
    """Nonzero boost must add boost once, rejecting boost*2 near-miss."""
    dossier, transcript, closed = artifacts
    hits = [i for i in closed["instances"] if i["boost"] != 0]
    assert len(hits) >= 40
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        rec = _tr_by_id(transcript, inst["instance_id"])
        doubled = (expected_slot(inst["left"], inst["right"]) + inst["nest_depth"] * 7 + inst["boost"] * 2) % 97
        want = expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
        assert row["boosted_score"] == want
        if doubled != want:
            assert row["boosted_score"] != doubled
        assert abs(float(rec["fuzz_margin_vector"][1])) <= 1e-9

def test_boost_rejects_depth_times_five(artifacts):
    """Depth coefficient must be 7, not a *5 near-miss."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if i["nest_depth"] != 0]
    for inst in hits[:80]:
        row = _row_by_id(dossier, inst["instance_id"])
        wrong = (expected_slot(inst["left"], inst["right"]) + inst["nest_depth"] * 5 + inst["boost"]) % 97
        want = expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
        assert row["boosted_score"] == want
        if wrong != want:
            assert row["boosted_score"] != wrong

def test_zero_boost_keeps_depth_term(artifacts):
    """Zero boost rows must still apply depth*7."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if i["boost"] == 0 and i["nest_depth"] != 0]
    assert len(hits) >= 5
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        flat = expected_slot(inst["left"], inst["right"])
        want = expected_boosted(inst["left"], inst["right"], inst["nest_depth"], 0)
        assert row["boosted_score"] == want
        assert row["boosted_score"] != flat

def test_depth_zero_nonzero_boost_shift(artifacts):
    """Depth-zero nonzero boost shifts by boost alone."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if i["nest_depth"] == 0 and i["boost"] != 0]
    assert len(hits) >= 3
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        flat = expected_slot(inst["left"], inst["right"])
        want = expected_boosted(inst["left"], inst["right"], 0, inst["boost"])
        assert row["boosted_score"] == want
        assert want != flat or inst["boost"] % 97 == 0

def test_boosted_range_universe(artifacts):
    """Every boosted_score stays in [0, 96]."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        assert 0 <= row["boosted_score"] < 97

def test_boosted_wrap_endpoint_zero(artifacts):
    """Corpus must include boosted_score wrap to 0 and report it."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if expected_boosted(i["left"], i["right"], i["nest_depth"], i["boost"]) == 0]
    assert len(hits) >= 5
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["boosted_score"] == 0

def test_boosted_wrap_endpoint_ninetysix(artifacts):
    """Corpus must include boosted_score wrap to 96 and report it."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if expected_boosted(i["left"], i["right"], i["nest_depth"], i["boost"]) == 96]
    assert len(hits) >= 5
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["boosted_score"] == 96

def test_high_depth_boost_wrap(artifacts):
    """nest_depth >= 8 rows must wrap boosted_score under mod 97."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if i["nest_depth"] >= 8]
    assert len(hits) >= 15
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])

def test_high_boost_alone_wrap(artifacts):
    """Large boost values must wrap with depth correctly under mod 97."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if i["boost"] >= 9]
    assert len(hits) >= 10
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])

def test_schedule_identity_margin1(artifacts):
    """margin_1 must encode boosted vs schedule identity from slot and boost."""
    dossier, transcript, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        rec = _tr_by_id(transcript, inst["instance_id"])
        sched = (row["slot_score"] + inst["nest_depth"] * 7 + inst["boost"]) % 97
        assert row["boosted_score"] == sched
        assert abs(float(rec["fuzz_margin_vector"][1])) <= 1e-9

def test_boost_rejects_depth_times_boost_product(artifacts):
    """Boosted path must not multiply depth by boost."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        if inst["nest_depth"] == 0 or inst["boost"] == 0:
            continue
        row = _row_by_id(dossier, inst["instance_id"])
        wrong = (expected_slot(inst["left"], inst["right"]) + inst["nest_depth"] * inst["boost"]) % 97
        want = expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
        assert row["boosted_score"] == want
        if wrong != want:
            assert row["boosted_score"] != wrong

def test_nest_depth_echo_on_row(artifacts):
    """Dossier nest_depth must echo the closed corpus nest_depth."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["nest_depth"] == inst["nest_depth"]

def test_graph_echo_on_row(artifacts):
    """Dossier graph must echo the closed corpus graph id."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["graph"] == inst["graph"]

def test_boosted_differs_from_slot_when_shifted(artifacts):
    """Any nonzero depth or boost must move boosted_score off flat slot when math says so."""
    dossier, _t, closed = artifacts
    moved = 0
    for inst in closed["instances"]:
        if inst["nest_depth"] == 0 and inst["boost"] == 0:
            continue
        row = _row_by_id(dossier, inst["instance_id"])
        want = expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
        flat = expected_slot(inst["left"], inst["right"])
        assert row["boosted_score"] == want
        if want != flat:
            assert row["boosted_score"] != row["slot_score"]
            moved += 1
    assert moved >= 40

def test_slot_unboosted_equals_depth_boost_zero_formula(artifacts):
    """slot_score equals zero-depth zero-boost pairing result for every closed row."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["slot_score"] == expected_boosted(inst["left"], inst["right"], 0, 0)

def test_gap_equals_pairing_boosted(artifacts):
    """Corpus gap residual must equal pairing-derived boosted_score."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        want = expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
        gap = expected_gap(inst["gap_a"], inst["gap_b"], inst["nest_depth"])
        row = _row_by_id(dossier, inst["instance_id"])
        assert want == gap
        assert row["boosted_score"] == want

def test_margin0_zero_all_closed(artifacts):
    """margin_0 must be ~0 for every closed instance."""
    _d, transcript, closed = artifacts
    for inst in closed["instances"]:
        rec = _tr_by_id(transcript, inst["instance_id"])
        assert abs(float(rec["fuzz_margin_vector"][0])) <= 1e-9

def test_margin1_zero_all_closed(artifacts):
    """margin_1 must be ~0 for every closed instance."""
    _d, transcript, closed = artifacts
    for inst in closed["instances"]:
        rec = _tr_by_id(transcript, inst["instance_id"])
        assert abs(float(rec["fuzz_margin_vector"][1])) <= 1e-9

def test_margin2_zero_all_closed(artifacts):
    """margin_2 must be ~0 for every closed instance."""
    _d, transcript, closed = artifacts
    for inst in closed["instances"]:
        rec = _tr_by_id(transcript, inst["instance_id"])
        assert abs(float(rec["fuzz_margin_vector"][2])) <= 1e-9

def test_fuzz_vector_length_three(artifacts):
    """Each fuzz_margin_vector must have exactly three components."""
    _d, transcript, closed = artifacts
    assert len(transcript["instances"]) == len(closed["instances"])
    for rec in transcript["instances"]:
        assert len(rec["fuzz_margin_vector"]) == 3

def test_verify_clean_requires_all_margins(artifacts):
    """verify_clean true only with all margin components near zero."""
    _d, transcript, _ = artifacts
    assert transcript.get("verify_clean") is True
    for rec in transcript["instances"]:
        assert all(abs(float(x)) <= 1e-9 for x in rec["fuzz_margin_vector"])

def test_gap_substitute_rejected_via_margin1(artifacts):
    """Writing gap into boosted while leaving slot wrong must not clear margin_1."""
    dossier, transcript, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        rec = _tr_by_id(transcript, inst["instance_id"])
        assert row["slot_score"] == expected_slot(inst["left"], inst["right"])
        assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
        assert abs(float(rec["fuzz_margin_vector"][0])) <= 1e-9
        assert abs(float(rec["fuzz_margin_vector"][1])) <= 1e-9

def test_margin2_requires_fragment_and_seal(artifacts):
    """margin_2 stays zero only when fragment and seal both match annex."""
    dossier, transcript, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        rec = _tr_by_id(transcript, inst["instance_id"])
        assert row["fragment_line"] == expected_fragment(inst["graph"], inst["nest_depth"])
        assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])
        assert abs(float(rec["fuzz_margin_vector"][2])) <= 1e-9

def test_transcript_instance_coverage(artifacts):
    """Transcript must cover exactly the closed instance ids."""
    _d, transcript, closed = artifacts
    closed_ids = {i["instance_id"] for i in closed["instances"]}
    tr_ids = {r["instance_id"] for r in transcript["instances"]}
    assert tr_ids == closed_ids

def test_obligation_ids_on_each_transcript_row(artifacts):
    """Each clean transcript row must list the full OBL-11 family."""
    _d, transcript, _c = artifacts
    needed = ["OBL-11", "OBL-11a", "OBL-11b", "OBL-11c"]
    for rec in transcript["instances"]:
        for item in needed:
            assert item in rec["obligation_ids_satisfied"]

def test_fragment_fnv_coeff_thirteen(artifacts):
    """Continuity must use depth*13, rejecting *11 near-miss tags."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        want = expected_fragment(inst["graph"], inst["nest_depth"])
        wrong = (fnv1a32(inst["graph"]) + inst["nest_depth"] * 11) % 100000
        wrong_line = f"G:{inst['graph']}|D:{inst['nest_depth']}|C:N{wrong}"
        assert row["fragment_line"] == want
        if inst["nest_depth"] != 0 and wrong_line != want:
            assert row["fragment_line"] != wrong_line

def test_fragment_rejects_depth_times_seventeen(artifacts):
    """Continuity must reject depth*17 near-miss coefficients."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        if inst["nest_depth"] == 0:
            continue
        row = _row_by_id(dossier, inst["instance_id"])
        wrong = (fnv1a32(inst["graph"]) + inst["nest_depth"] * 17) % 100000
        wrong_line = f"G:{inst['graph']}|D:{inst['nest_depth']}|C:N{wrong}"
        want = expected_fragment(inst["graph"], inst["nest_depth"])
        assert row["fragment_line"] == want
        if wrong_line != want:
            assert row["fragment_line"] != wrong_line

def test_fragment_has_three_pipe_fields(artifacts):
    """Fragment lines must be exactly G|D|C fields with two separators."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        parts = row["fragment_line"].split("|")
        want_parts = expected_fragment(inst["graph"], inst["nest_depth"]).split("|")
        assert len(parts) == 3
        assert parts[0] == want_parts[0]
        assert parts[1] == want_parts[1]
        assert parts[2] == want_parts[2]

def test_fragment_deep_no_extra_suffix(artifacts):
    """Deep nests must not append extra suffix fields after continuity."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if i["nest_depth"] > 8]
    assert len(hits) >= 10
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["fragment_line"] == expected_fragment(inst["graph"], inst["nest_depth"])
        assert len(row["fragment_line"].split("|")) == 3

def test_fragment_continuity_numeric_mod_1e5(artifacts):
    """Continuity numeric tag must equal FNV+depth*13 mod 100000."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        want = expected_fragment(inst["graph"], inst["nest_depth"])
        assert row["fragment_line"] == want
        cpart = want.split("|", 2)[2]
        assert row["fragment_line"].split("|", 2)[2] == cpart
        int(cpart[3:])

def test_fragment_ns7_family(artifacts):
    """Largest closed graph family must keep per-row annex continuity."""
    dossier, _t, closed = artifacts
    graphs: dict[str, int] = {}
    for inst in closed["instances"]:
        g = inst["graph"]
        graphs[g] = graphs.get(g, 0) + 1
    graph = max(graphs, key=lambda g: graphs[g])
    hits = [i for i in closed["instances"] if i["graph"] == graph]
    assert len(hits) >= 20
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["fragment_line"].startswith(f"G:{graph}|")
        assert row["fragment_line"] == expected_fragment(graph, inst["nest_depth"])

def test_fragment_ns9_family(artifacts):
    """Second-largest closed graph family must keep per-row annex continuity."""
    dossier, _t, closed = artifacts
    graphs: dict[str, int] = {}
    for inst in closed["instances"]:
        g = inst["graph"]
        graphs[g] = graphs.get(g, 0) + 1
    ordered = sorted(graphs, key=lambda g: graphs[g], reverse=True)
    assert len(ordered) >= 2
    graph = ordered[1]
    hits = [i for i in closed["instances"] if i["graph"] == graph]
    assert len(hits) >= 20
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["fragment_line"].startswith(f"G:{graph}|")
        assert row["fragment_line"] == expected_fragment(graph, inst["nest_depth"])

def test_fragment_rejects_missing_continuity_prefix(artifacts):
    """Fragment must include continuity field, not bare G|D only."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        bare = f"G:{inst['graph']}|D:{inst['nest_depth']}"
        want = expected_fragment(inst["graph"], inst["nest_depth"])
        assert row["fragment_line"] != bare
        assert row["fragment_line"] == want
        assert len(row["fragment_line"].split("|")) == 3

def test_fragment_depth_digits_match_corpus(artifacts):
    """Fragment D field digits must match corpus nest_depth."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        dpart = row["fragment_line"].split("|")[1]
        assert dpart == f"D:{inst['nest_depth']}"

def test_fragment_rejects_fnv_without_depth(artifacts):
    """Continuity must include depth term, not FNV alone."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        if inst["nest_depth"] == 0:
            continue
        row = _row_by_id(dossier, inst["instance_id"])
        wrong = fnv1a32(inst["graph"]) % 100000
        wrong_line = f"G:{inst['graph']}|D:{inst['nest_depth']}|C:N{wrong}"
        want = expected_fragment(inst["graph"], inst["nest_depth"])
        assert row["fragment_line"] == want
        if wrong_line != want:
            assert row["fragment_line"] != wrong_line

def test_payload_embeds_fragment_verbatim(artifacts):
    """row_payload third field must equal fragment_line exactly."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        parts = row["row_payload"].split("|", 2)
        assert parts[2] == row["fragment_line"]

def test_payload_embeds_boosted_decimal(artifacts):
    """row_payload middle field must be decimal boosted_score."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        parts = row["row_payload"].split("|", 2)
        assert int(parts[1]) == row["boosted_score"]

def test_seal_separator_0x1f(artifacts):
    """Seal material must use 0x1F, rejecting 0x1E near-miss."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        payload = expected_payload(inst["instance_id"], row["boosted_score"], row["fragment_line"])
        ctx = expected_ctx(inst["graph"], inst["nest_depth"])
        assert row["seal_hex"] == expected_seal(payload, ctx)
        wrong = sha256_hex(bytes(payload, "utf-8") + b"\x1e" + bytes(ctx, "utf-8"))
        assert row["seal_hex"] != wrong

def test_seal_rejects_payload_only(artifacts):
    """Seal must mix ctx_tag; payload-only sha256 must not match."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["seal_hex"] != payload_only_digest(row["row_payload"])

def test_seal_rejects_concatenation_without_separator(artifacts):
    """Seal must not be sha256(payload+ctx) without the unit separator."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        concat = sha256_hex(row["row_payload"] + row["ctx_tag"])
        assert row["seal_hex"] != concat

def test_seal_rejects_ctx_before_payload(artifacts):
    """Seal must not reverse material order to ctx then payload."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        rev = sha256_hex(bytes(row["ctx_tag"], "utf-8") + b"\x1f" + bytes(row["row_payload"], "utf-8"))
        assert row["seal_hex"] != rev

def test_ctx_tag_graph_depth_form(artifacts):
    """ctx_tag must be graph:nest_depth."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["ctx_tag"] == expected_ctx(inst["graph"], inst["nest_depth"])

def test_shared_ctx_distinct_seals(artifacts):
    """Rows sharing ctx_tag but different payloads must keep distinct seals."""
    dossier, _t, closed = artifacts
    by_ctx = {}
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        key = row["ctx_tag"]
        if key not in by_ctx:
            by_ctx[key] = []
        by_ctx[key].append(row)
    multi = [rows for rows in by_ctx.values() if len(rows) >= 2]
    assert len(multi) >= 5
    for rows in multi:
        assert len({r["row_payload"] for r in rows}) == len(rows)
        assert len({r["seal_hex"] for r in rows}) == len(rows)

def test_payload_instance_id_prefix(artifacts):
    """row_payload must start with instance_id before the first pipe."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["row_payload"].split("|", 1)[0] == inst["instance_id"]

def test_payload_full_triple_contract(artifacts):
    """row_payload must equal instance_id|boosted|fragment."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["row_payload"] == expected_payload(inst["instance_id"], row["boosted_score"], row["fragment_line"])

def test_seal_hex_length_64(artifacts):
    """Every seal_hex must be 64 lowercase hex characters."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        assert len(row["seal_hex"]) == 64
        assert row["seal_hex"] == row["seal_hex"].lower()
        int(row["seal_hex"], 16)

def test_seal_deterministic_across_rows_formula(artifacts):
    """Seal of reported payload/ctx must match annex sha256 materialization."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])

def test_seal_changes_when_boosted_changes(artifacts):
    """Different boosted_score values must yield different seals for same graph depth family when payloads differ."""
    dossier, _t, closed = artifacts
    # pick two rows same graph+depth different boosted if available
    groups = {}
    for inst in closed["instances"]:
        key = (inst["graph"], inst["nest_depth"])
        if key not in groups:
            groups[key] = []
        groups[key].append(inst)
    checked = 0
    for members in groups.values():
        if len(members) < 2:
            continue
        rows = [_row_by_id(dossier, m["instance_id"]) for m in members]
        if len({r["boosted_score"] for r in rows}) < 2:
            continue
        assert len({r["seal_hex"] for r in rows}) == len(rows)
        checked += 1
    assert checked >= 3

def test_ctx_rejects_slash_separator(artifacts):
    """ctx_tag must use colon, not slash, between graph and depth."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["ctx_tag"] != slash_ctx(inst["graph"], inst["nest_depth"])
        assert row["ctx_tag"] == expected_ctx(inst["graph"], inst["nest_depth"])

def test_payload_rejects_slot_in_middle_field(artifacts):
    """Middle payload field must be boosted_score, not slot_score, when they differ."""
    dossier, _t, closed = artifacts
    moved = 0
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        if row["slot_score"] == row["boosted_score"]:
            continue
        parts = row["row_payload"].split("|", 2)
        assert int(parts[1]) == row["boosted_score"]
        assert int(parts[1]) != row["slot_score"]
        moved += 1
    assert moved >= 40

def test_arm_omit_seal_separator(artifacts):
    """Arm-omit seals must also use 0x1F mixing."""
    dossier, _t, _c = artifacts
    for ao in _arm_cases():
        row = _row_by_id(dossier, ao["case_id"])
        assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])
        wrong = sha256_hex(bytes(row["row_payload"], "utf-8") + b"\x1e" + bytes(row["ctx_tag"], "utf-8"))
        assert row["seal_hex"] != wrong

def test_arm_omit_ctx_form(artifacts):
    """Arm-omit ctx_tag must follow graph:depth."""
    dossier, _t, _c = artifacts
    for ao in _arm_cases():
        row = _row_by_id(dossier, ao["case_id"])
        assert row["ctx_tag"] == expected_ctx(ao["graph"], ao["nest_depth"])

def test_trace_span_sorted_json_array(artifacts):
    """trace_span_digest must hash sorted seal_hex JSON array, not concatenation."""
    dossier, _t, _c = artifacts
    seals = sorted(r["seal_hex"] for r in dossier["dossier_rows"])
    compact = sha256_hex(json.dumps(seals, separators=(",", ":")))
    spaced = sha256_hex(json.dumps(seals))
    assert dossier["trace_span_digest"] in (compact, spaced)
    assert dossier["trace_span_digest"] != sha256_hex("".join(seals))

def test_trace_span_digest_length(artifacts):
    """trace_span_digest must be 64 hex chars."""
    dossier, _t, _c = artifacts
    assert len(dossier["trace_span_digest"]) == 64

def test_trace_span_includes_arm_omit_seals(artifacts):
    """trace_span_digest input must include arm-omit row seals."""
    dossier, _t, _c = artifacts
    arm_ids = {ao["case_id"] for ao in _arm_cases()}
    seals = [r["seal_hex"] for r in dossier["dossier_rows"] if r["instance_id"] in arm_ids]
    assert len(seals) == len(arm_ids)
    assert len(set(seals)) == len(seals)

def test_replay_digest_triple(artifacts):
    """replay_digest must be sha256(instance_id|seal_hex|fragment_line)."""
    dossier, transcript, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        rec = _tr_by_id(transcript, inst["instance_id"])
        src = f"{inst['instance_id']}|{row['seal_hex']}|{row['fragment_line']}"
        assert rec["replay_digest"] == sha256_hex(src)

def test_replay_digest_rejects_seal_only(artifacts):
    """replay_digest must not equal seal_hex or sha256(seal_hex)."""
    dossier, transcript, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        rec = _tr_by_id(transcript, inst["instance_id"])
        assert rec["replay_digest"] != row["seal_hex"]
        assert rec["replay_digest"] != sha256_hex(row["seal_hex"])

def test_idempotent_seals(artifacts):
    """Second emit+verify must reproduce identical seals."""
    dossier1, _t1, _c = artifacts
    run_emit_verify()
    dossier2 = json.loads(DOSSIER.read_text())
    d1 = {r["instance_id"]: r["seal_hex"] for r in dossier1["dossier_rows"]}
    d2 = {r["instance_id"]: r["seal_hex"] for r in dossier2["dossier_rows"]}
    assert d1 == d2

def test_idempotent_trace_span(artifacts):
    """Second emit must reproduce identical trace_span_digest."""
    dossier1, _t1, _c = artifacts
    run_emit_verify()
    dossier2 = json.loads(DOSSIER.read_text())
    assert dossier1["trace_span_digest"] == dossier2["trace_span_digest"]

def test_idempotent_replay_digests(artifacts):
    """Second verify must reproduce identical replay digests."""
    _d1, transcript1, _c = artifacts
    run_emit_verify()
    transcript2 = json.loads(TRANSCRIPT.read_text())
    t1 = {r["instance_id"]: r["replay_digest"] for r in transcript1["instances"]}
    t2 = {r["instance_id"]: r["replay_digest"] for r in transcript2["instances"]}
    assert t1 == t2

def test_perm_orders_cover_closed_ids(artifacts):
    """Every permutation stress order must cover exactly closed ids."""
    _d, _t, closed = artifacts
    ids = {i["instance_id"] for i in closed["instances"]}
    orders = [json.loads(line) for line in PERM.read_text().splitlines() if line.strip()]
    assert len(orders) >= 5
    for o in orders:
        assert set(o["order"]) == ids
        assert len(o["order"]) == len(ids)

def test_perm_cannot_invent_green_via_reorder_alone(artifacts):
    """Closed seals must remain ctx-mixed regardless of perm corpus presence."""
    dossier, _t, closed = artifacts
    ids = {i["instance_id"] for i in closed["instances"]}
    for row in dossier["dossier_rows"]:
        if row["instance_id"] not in ids:
            continue
        assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])

def test_arm_omit_instance_id_mapping(artifacts):
    """Arm-omit case keys must appear as dossier instance_id values."""
    dossier, _t, _c = artifacts
    for ao in _arm_cases():
        row = _row_by_id(dossier, ao["case_id"])
        assert row is not None
        assert row["instance_id"] == ao["case_id"]

def test_arm_omit_slot_scores(artifacts):
    """Arm-omit slot_score must follow annex pairing."""
    dossier, _t, _c = artifacts
    for ao in _arm_cases():
        row = _row_by_id(dossier, ao["case_id"])
        assert row["slot_score"] == expected_slot(ao["left"], ao["right"])

def test_arm_omit_boosted_scores(artifacts):
    """Arm-omit boosted_score must follow annex depth/boost shift."""
    dossier, _t, _c = artifacts
    for ao in _arm_cases():
        row = _row_by_id(dossier, ao["case_id"])
        assert row["boosted_score"] == expected_boosted(ao["left"], ao["right"], ao["nest_depth"], ao["boost"])

def test_arm_omit_fragments(artifacts):
    """Arm-omit fragment lines must match annex continuity."""
    dossier, _t, _c = artifacts
    for ao in _arm_cases():
        row = _row_by_id(dossier, ao["case_id"])
        assert row["fragment_line"] == expected_fragment(ao["graph"], ao["nest_depth"])

def test_arm_omit_payloads(artifacts):
    """Arm-omit payloads must embed case key, boosted, and fragment."""
    dossier, _t, _c = artifacts
    for ao in _arm_cases():
        row = _row_by_id(dossier, ao["case_id"])
        assert row["row_payload"] == expected_payload(ao["case_id"], row["boosted_score"], row["fragment_line"])

def test_arm_omit_omitted_in_edge_arms(artifacts):
    """Each omitted_arm must appear inside edge_arms."""
    dossier, _t, _c = artifacts
    for ao in _arm_cases():
        row = _row_by_id(dossier, ao["case_id"])
        assert ao["omitted_arm"] in row["edge_arms"]

def test_arm_omit_core_present(artifacts):
    """Arm-omit edge_arms must include core."""
    dossier, _t, _c = artifacts
    for ao in _arm_cases():
        row = _row_by_id(dossier, ao["case_id"])
        assert "core" in row["edge_arms"]

def test_arm_omit_rejects_swapped_pairing(artifacts):
    """Arm-omit asymmetric rows must reject swapped pairing near-miss."""
    dossier, _t, _c = artifacts
    hits = [ao for ao in _arm_cases() if ao["left"] != ao["right"]]
    assert len(hits) >= 10
    for ao in hits:
        row = _row_by_id(dossier, ao["case_id"])
        want = expected_slot(ao["left"], ao["right"])
        assert row["slot_score"] == want
        if want != swapped_slot(ao["left"], ao["right"]):
            assert row["slot_score"] != swapped_slot(ao["left"], ao["right"])

def test_arm_omit_rejects_doubled_boost(artifacts):
    """Arm-omit nonzero boost rows must reject boost*2 near-miss."""
    dossier, _t, _c = artifacts
    hits = [ao for ao in _arm_cases() if ao["boost"] != 0]
    assert len(hits) >= 5
    for ao in hits:
        row = _row_by_id(dossier, ao["case_id"])
        want = expected_boosted(ao["left"], ao["right"], ao["nest_depth"], ao["boost"])
        doubled = (expected_slot(ao["left"], ao["right"]) + ao["nest_depth"] * 7 + ao["boost"] * 2) % 97
        assert row["boosted_score"] == want
        if doubled != want:
            assert row["boosted_score"] != doubled

def test_arm_omit_scale(artifacts):
    """Arm-omit corpus must remain at operational scale."""
    _d, _t, _c = artifacts
    assert len(_arm_cases()) >= 30

def test_obligation_coverage_family(artifacts):
    """Dossier obligation_coverage must include the full OBL-11 family."""
    dossier, _t, _c = artifacts
    for item in ["OBL-11", "OBL-11a", "OBL-11b", "OBL-11c"]:
        assert item in dossier["obligation_coverage"]

def test_suite_a_members_present(artifacts):
    """suite_a closed members must appear in dossier rows."""
    dossier, _t, closed = artifacts
    members = [i for i in closed["instances"] if i["suite"] == "suite_a"]
    assert len(members) >= 15
    for inst in members:
        assert _row_by_id(dossier, inst["instance_id"]) is not None

def test_suite_b_members_present(artifacts):
    """suite_b closed members must appear in dossier rows."""
    dossier, _t, closed = artifacts
    members = [i for i in closed["instances"] if i["suite"] == "suite_b"]
    assert len(members) >= 15
    for inst in members:
        assert _row_by_id(dossier, inst["instance_id"]) is not None

def test_suite_c_members_present(artifacts):
    """suite_c closed members must appear in dossier rows."""
    dossier, _t, closed = artifacts
    members = [i for i in closed["instances"] if i["suite"] == "suite_c"]
    assert len(members) >= 15
    for inst in members:
        assert _row_by_id(dossier, inst["instance_id"]) is not None

def test_closed_corpus_minimum_scale(artifacts):
    """Closed corpus must stay large for stress coverage."""
    _d, _t, closed = artifacts
    assert len(closed["instances"]) >= 150

def test_dossier_row_count_closed_plus_arm(artifacts):
    """Dossier rows must equal closed union arm-omit ids."""
    dossier, _t, closed = artifacts
    closed_ids = {i["instance_id"] for i in closed["instances"]}
    arm_ids = {ao["case_id"] for ao in _arm_cases()}
    row_ids = {r["instance_id"] for r in dossier["dossier_rows"]}
    assert row_ids == closed_ids | arm_ids

def test_depth_diversity_span(artifacts):
    """Closed depths must span from below 1 through at least 10."""
    _d, _t, closed = artifacts
    depths = {i["nest_depth"] for i in closed["instances"]}
    assert min(depths) < 1
    assert max(depths) >= 10

def test_boost_diversity_span(artifacts):
    """Closed boosts must include low and high values."""
    _d, _t, closed = artifacts
    boosts = {i["boost"] for i in closed["instances"]}
    assert min(boosts) < 1
    assert max(boosts) >= 9

def test_metamorphic_same_inputs_same_slot(artifacts):
    """Identical left/right pairs across rows must share slot_score."""
    dossier, _t, closed = artifacts
    groups = {}
    for inst in closed["instances"]:
        key = (inst["left"], inst["right"])
        if key not in groups:
            groups[key] = []
        groups[key].append(inst)
    checked = 0
    for members in groups.values():
        if len(members) < 2:
            continue
        scores = {_row_by_id(dossier, m["instance_id"])["slot_score"] for m in members}
        assert len(scores) == 1
        checked += 1
    assert checked >= 5

def test_metamorphic_same_graph_depth_same_fragment(artifacts):
    """Identical graph+depth must share fragment_line across rows."""
    dossier, _t, closed = artifacts
    groups = {}
    for inst in closed["instances"]:
        key = (inst["graph"], inst["nest_depth"])
        if key not in groups:
            groups[key] = []
        groups[key].append(inst)
    checked = 0
    for members in groups.values():
        if len(members) < 2:
            continue
        frags = {_row_by_id(dossier, m["instance_id"])["fragment_line"] for m in members}
        assert len(frags) == 1
        checked += 1
    assert checked >= 5

def test_closed_no_duplicate_instance_ids(artifacts):
    """Closed corpus instance_id values must be unique."""
    _d, _t, closed = artifacts
    ids = [i["instance_id"] for i in closed["instances"]]
    assert len(ids) == len(set(ids))

def test_dossier_no_duplicate_instance_ids(artifacts):
    """Dossier rows must not duplicate instance_id."""
    dossier, _t, _c = artifacts
    ids = [r["instance_id"] for r in dossier["dossier_rows"]]
    assert len(ids) == len(set(ids))

def test_replay_changes_with_fragment(artifacts):
    """replay_digest must depend on fragment_line, not seal alone."""
    dossier, transcript, closed = artifacts
    for inst in closed["instances"][:40]:
        row = _row_by_id(dossier, inst["instance_id"])
        rec = _tr_by_id(transcript, inst["instance_id"])
        alt = sha256_hex(f"{inst['instance_id']}|{row['seal_hex']}|ALT")
        assert rec["replay_digest"] != alt

def test_ns7_depth_ten_family_if_present(artifacts):
    """Deep rows on the largest graph family must match annex continuity and boost."""
    dossier, _t, closed = artifacts
    graphs: dict[str, int] = {}
    for inst in closed["instances"]:
        g = inst["graph"]
        graphs[g] = graphs.get(g, 0) + 1
    graph = max(graphs, key=lambda g: graphs[g])
    hits = [i for i in closed["instances"] if i["graph"] == graph and i["nest_depth"] >= 10]
    assert len(hits) >= 1
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["fragment_line"] == expected_fragment(graph, inst["nest_depth"])
        assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])

def test_ns9_depth_ten_family_if_present(artifacts):
    """Deep rows on the second-largest graph family must match annex continuity and boost."""
    dossier, _t, closed = artifacts
    graphs: dict[str, int] = {}
    for inst in closed["instances"]:
        g = inst["graph"]
        graphs[g] = graphs.get(g, 0) + 1
    ordered = sorted(graphs, key=lambda g: graphs[g], reverse=True)
    assert len(ordered) >= 2
    graph = ordered[1]
    hits = [i for i in closed["instances"] if i["graph"] == graph and i["nest_depth"] >= 10]
    assert len(hits) >= 1
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["fragment_line"] == expected_fragment(graph, inst["nest_depth"])
        assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])

def test_high_slot_and_nonzero_boost_combo(artifacts):
    """High slot residues with nonzero boost must keep both pairing and boost terms."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if expected_slot(i["left"], i["right"]) > 90 and i["boost"] != 0]
    assert len(hits) >= 5
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["slot_score"] == expected_slot(inst["left"], inst["right"])
        assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])

def test_verify_clean_false_would_require_nonzero_margin(artifacts):
    """When verify_clean is true, no transcript margin component may exceed tolerance."""
    _d, transcript, _c = artifacts
    assert transcript.get("verify_clean") is True
    for rec in transcript["instances"]:
        for x in rec["fuzz_margin_vector"]:
            assert abs(float(x)) <= 1e-9

def test_closed_arm_disjoint_ids(artifacts):
    """Closed instance_id values must not collide with arm-omit case ids."""
    _d, _t, closed = artifacts
    closed_ids = {i["instance_id"] for i in closed["instances"]}
    arm_ids = {ao["case_id"] for ao in _arm_cases()}
    assert not (closed_ids & arm_ids)



def test_equal_index_rejects_additive_fast_path(artifacts):
    """Equal left/right indices must still use product pairing, not additive."""
    dossier, _t, closed = artifacts
    equals = [i for i in closed["instances"] if i["left"] == i["right"]]
    assert len(equals) >= 5
    discriminated = 0
    for inst in equals:
        row = _row_by_id(dossier, inst["instance_id"])
        want = expected_slot(inst["left"], inst["right"])
        assert row["slot_score"] == want
        additive = equal_additive_slot(inst["left"], inst["right"])
        if additive != want:
            assert row["slot_score"] != additive
            discriminated += 1
    assert discriminated >= 5


def test_journal_epoch_present(artifacts):
    """Dossier must publish journal_epoch as a positive integer."""
    dossier, _t, _c = artifacts
    assert isinstance(dossier["journal_epoch"], int)
    assert dossier["journal_epoch"] >= 1


def test_shard_manifest_four_members(artifacts):
    """shard_manifest must list the four journal shard names from the annex."""
    dossier, _t, _c = artifacts
    annex = (APP / "annex" / "margin_contract.inc").read_text()
    # Discover names from the annex shard_manifest example list.
    start = annex.index('["suite_a"')
    end = annex.index("]", start) + 1
    # Normalize to plain strings for comparison with JSON list values.
    raw = annex[start:end].replace('"', "")
    expect = [p.strip() for p in raw.strip("[]").split(",")]
    assert dossier["shard_manifest"] == expect


def test_journal_files_exist(artifacts):
    """All four journal shard files must exist after emit."""
    _d, _t, _c = artifacts
    for name in ("suite_a.jsonl", "suite_b.jsonl", "suite_c.jsonl", "arm_omit.jsonl"):
        assert (JOURNAL / name).exists()


def test_journal_epoch_matches_stamp(artifacts):
    """dossier journal_epoch must match the on-disk epoch stamp."""
    _d, _t, _c = artifacts
    run_emit_verify()
    dossier = json.loads(DOSSIER.read_text())
    assert STAMP.exists()
    assert int(STAMP.read_text().strip()) == dossier["journal_epoch"]


def test_arm_omit_survives_journal_merge(artifacts):
    """Every arm-omit case_id must appear in merged dossier_rows."""
    dossier, _t, _c = artifacts
    for ao in _arm_cases():
        assert _row_by_id(dossier, ao["case_id"]) is not None


def test_edge_arms_survive_journaling(artifacts):
    """edge_arms must remain on every dossier row after journal merge."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        assert "edge_arms" in row
        assert isinstance(row["edge_arms"], list)
        assert "core" in row["edge_arms"]
    for ao in _arm_cases():
        row = _row_by_id(dossier, ao["case_id"])
        assert "edge_arms" in row
        assert ao["omitted_arm"] in row["edge_arms"]


def test_stale_epoch_lines_excluded(artifacts):
    """Dossier membership must come only from the current journal epoch."""
    _d, _t, _c = artifacts
    run_emit_verify()
    dossier = json.loads(DOSSIER.read_text())
    epoch = dossier["journal_epoch"]
    dossier_ids = {r["instance_id"] for r in dossier["dossier_rows"]}
    for inst_id in dossier_ids:
        matched = False
        for name in ("suite_a.jsonl", "suite_b.jsonl", "suite_c.jsonl", "arm_omit.jsonl"):
            for line in _load_shard(name):
                if line.get("instance_id") == inst_id and line.get("epoch") == epoch:
                    matched = True
                    break
            if matched:
                break
        assert matched, inst_id

def test_closed_suite_shards_nonempty(artifacts):
    """Each suite shard must carry at least one current-epoch closed row."""
    _d, _t, closed = artifacts
    run_emit_verify()
    dossier = json.loads(DOSSIER.read_text())
    epoch = dossier["journal_epoch"]
    by_suite = {"suite_a": 0, "suite_b": 0, "suite_c": 0}
    for inst in closed["instances"]:
        by_suite[inst["suite"]] += 1
    for suite, n in by_suite.items():
        assert n >= 1
        lines = [x for x in _load_shard(f"{suite}.jsonl") if x.get("epoch") == epoch]
        assert len(lines) >= 1


def test_arm_omit_shard_nonempty(artifacts):
    """arm_omit.jsonl must contain every arm-omit case for the current epoch."""
    _d, _t, _c = artifacts
    run_emit_verify()
    dossier = json.loads(DOSSIER.read_text())
    epoch = dossier["journal_epoch"]
    lines = [x for x in _load_shard("arm_omit.jsonl") if x.get("epoch") == epoch]
    ids = {x["instance_id"] for x in lines}
    for ao in _arm_cases():
        assert ao["case_id"] in ids


def test_recovery_digest_sorted_replay_array(artifacts):
    """recovery_digest must hash the sorted JSON array of closed replay digests."""
    _d, transcript, closed = artifacts
    replays = []
    for inst in closed["instances"]:
        rec = _tr_by_id(transcript, inst["instance_id"])
        replays.append(rec["replay_digest"])
    replays.sort()
    assert transcript["recovery_digest"] == sha256_hex(json.dumps(replays, separators=(",", ":")))


def test_dossier_includes_all_closed_after_merge(artifacts):
    """Merged dossier must include every closed instance_id."""
    dossier, _t, closed = artifacts
    ids = {r["instance_id"] for r in dossier["dossier_rows"]}
    for inst in closed["instances"]:
        assert inst["instance_id"] in ids


def test_journal_line_epoch_matches_dossier(artifacts):
    """Each dossier row must have a matching current-epoch journal line with same seal."""
    _d, _t, _c = artifacts
    run_emit_verify()
    dossier = json.loads(DOSSIER.read_text())
    epoch = dossier["journal_epoch"]
    for row in dossier["dossier_rows"]:
        hits = []
        for name in ("suite_a.jsonl", "suite_b.jsonl", "suite_c.jsonl", "arm_omit.jsonl"):
            for line in _load_shard(name):
                if line.get("instance_id") == row["instance_id"] and line.get("epoch") == epoch:
                    hits.append(line)
        assert len(hits) == 1
        assert hits[0]["seal_hex"] == row["seal_hex"]


def test_seal_cache_clears_across_epoch(artifacts):
    """A second emit advancing the epoch must keep seals payload-correct."""
    dossier1, _t1, closed = artifacts
    run_emit_verify()
    dossier2 = json.loads(DOSSIER.read_text())
    assert dossier2["journal_epoch"] > dossier1["journal_epoch"]
    for inst in closed["instances"]:
        row = _row_by_id(dossier2, inst["instance_id"])
        assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])


def test_recovery_digest_length_64(artifacts):
    """recovery_digest must be a 64-char lowercase hex string."""
    _d, transcript, _c = artifacts
    assert len(transcript["recovery_digest"]) == 64
    int(transcript["recovery_digest"], 16)


def test_recovery_digest_rejects_unsorted(artifacts):
    """recovery_digest must not equal the hash of unsorted replay digests."""
    _d, transcript, closed = artifacts
    replays = [_tr_by_id(transcript, i["instance_id"])["replay_digest"] for i in closed["instances"]]
    unsorted = sha256_hex(json.dumps(replays, separators=(",", ":")))
    if replays != sorted(replays):
        assert transcript["recovery_digest"] != unsorted


def test_closed_row_count_matches_corpus(artifacts):
    """Dossier closed membership equals closed corpus size plus arm-omit size."""
    dossier, _t, closed = artifacts
    assert len(dossier["dossier_rows"]) == len(closed["instances"]) + len(_arm_cases())


def test_slot_score_range_all_rows(artifacts):
    """Every slot_score must lie in 0..96 inclusive."""
    dossier, _t, _c = artifacts
    for row in dossier["dossier_rows"]:
        assert 0 <= row["slot_score"] <= 96


def test_boosted_score_range_all_rows(artifacts):
    """Every boosted_score must lie in 0..96 inclusive."""
    dossier, _t, _c = artifacts
    for row in dossier["dossier_rows"]:
        assert 0 <= row["boosted_score"] <= 96


def test_payload_rejects_wrong_separator_colon(artifacts):
    """row_payload must use pipe separators, not colon triples."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        bad = f"{inst['instance_id']}:{row['boosted_score']}:{row['fragment_line']}"
        assert row["row_payload"] != bad


def test_ctx_rejects_dash_separator(artifacts):
    """ctx_tag must use colon, not dash, between graph and depth."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["ctx_tag"] != f"{inst['graph']}-{inst['nest_depth']}"
        assert row["ctx_tag"] == expected_ctx(inst["graph"], inst["nest_depth"])


def test_fragment_rejects_depth_times_eleven(artifacts):
    """Continuity must use depth*13, not the near-miss depth*11 coefficient."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        wrong = (fnv1a32(inst["graph"]) + inst["nest_depth"] * 11) % 100000
        assert f"C:N{wrong}" not in row["fragment_line"] or row["fragment_line"] == expected_fragment(
            inst["graph"], inst["nest_depth"]
        )
        assert row["fragment_line"] == expected_fragment(inst["graph"], inst["nest_depth"])


def test_boost_rejects_plus_depth_only_without_boost(artifacts):
    """When boost is nonzero, boosted must not ignore the boost term."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if i["boost"] != 0]
    assert len(hits) >= 20
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        without = (expected_slot(inst["left"], inst["right"]) + inst["nest_depth"] * 7) % 97
        assert row["boosted_score"] == expected_boosted(
            inst["left"], inst["right"], inst["nest_depth"], inst["boost"]
        )
        if without != row["boosted_score"]:
            assert row["boosted_score"] != without


def test_margin0_matches_gap_formula(artifacts):
    """margin_0 must be exactly reported boosted minus expected_gap."""
    dossier, transcript, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        rec = _tr_by_id(transcript, inst["instance_id"])
        want = float(row["boosted_score"] - expected_gap(inst["gap_a"], inst["gap_b"], inst["nest_depth"]))
        assert rec["fuzz_margin_vector"][0] == want


def test_margin1_matches_schedule_formula(artifacts):
    """margin_1 must be boosted minus the annex schedule shift of slot/depth/boost."""
    dossier, transcript, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        rec = _tr_by_id(transcript, inst["instance_id"])
        sched = (row["slot_score"] + inst["nest_depth"] * 7 + inst["boost"]) % 97
        want = float(row["boosted_score"] - sched)
        assert rec["fuzz_margin_vector"][1] == want


def test_shared_ctx_distinct_payloads_many(artifacts):
    """At least five shared ctx_tag groups must still yield distinct seals."""
    dossier, _t, closed = artifacts
    from collections import defaultdict

    groups = defaultdict(list)
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        groups[row["ctx_tag"]].append(row)
    multi = [g for g in groups.values() if len(g) >= 2]
    assert len(multi) >= 5
    for g in multi:
        seals = {r["seal_hex"] for r in g}
        payloads = {r["row_payload"] for r in g}
        if len(payloads) > 1:
            assert len(seals) == len(payloads)


def test_arm_omit_edge_arms_exactly_core_and_omitted(artifacts):
    """Arm-omit edge_arms must be exactly {core, omitted_arm} as a set."""
    dossier, _t, _c = artifacts
    for ao in _arm_cases():
        row = _row_by_id(dossier, ao["case_id"])
        assert set(row["edge_arms"]) == {"core", ao["omitted_arm"]}


def test_closed_edge_arms_include_core_west_east(artifacts):
    """Closed rows must expose the full core/west/east arm set."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        assert set(row["edge_arms"]) == {"core", "west", "east"}


def test_trace_span_includes_all_row_seals(artifacts):
    """trace_span_digest must cover every dossier row seal, sorted."""
    dossier, _t, _c = artifacts
    seals = sorted(r["seal_hex"] for r in dossier["dossier_rows"])
    assert dossier["trace_span_digest"] == sha256_hex(json.dumps(seals, separators=(",", ":")))


def test_idempotent_recovery_digest(artifacts):
    """Second emit+verify must keep recovery_digest stable."""
    _d, t1, _c = artifacts
    run_emit_verify()
    t2 = json.loads(TRANSCRIPT.read_text())
    assert t1["recovery_digest"] == t2["recovery_digest"]


def test_idempotent_journal_epoch_advances(artifacts):
    """Each emit must advance journal_epoch while preserving row semantics."""
    _d0, _t, closed = artifacts
    run_emit_verify()
    d1 = json.loads(DOSSIER.read_text())
    run_emit_verify()
    d2 = json.loads(DOSSIER.read_text())
    assert d2["journal_epoch"] == d1["journal_epoch"] + 1
    for inst in closed["instances"]:
        r1 = _row_by_id(d1, inst["instance_id"])
        r2 = _row_by_id(d2, inst["instance_id"])
        assert r1["slot_score"] == r2["slot_score"]
        assert r1["boosted_score"] == r2["boosted_score"]
        assert r1["fragment_line"] == r2["fragment_line"]
        assert r1["seal_hex"] == r2["seal_hex"]


def test_depth_zero_boost_zero_identity_many(artifacts):
    """depth=0 boost=0 rows must keep boosted_score equal to slot_score."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if i["nest_depth"] == 0 and i["boost"] == 0]
    assert len(hits) >= 1
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["boosted_score"] == row["slot_score"]


def test_high_boost_wrap_family(artifacts):
    """Large boost values must wrap mod 97 without clamping."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if i["boost"] >= 20]
    assert len(hits) >= 5
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["boosted_score"] == expected_boosted(
            inst["left"], inst["right"], inst["nest_depth"], inst["boost"]
        )


def test_deep_nest_fragment_no_trim_suffix(artifacts):
    """Deep nest depths must not append trim/extra fragment suffixes."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if i["nest_depth"] > 8]
    assert len(hits) >= 5
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        assert "|X:" not in row["fragment_line"]
        assert row["fragment_line"] == expected_fragment(inst["graph"], inst["nest_depth"])


def test_seal_rejects_0x1e_separator(artifacts):
    """Seals must not use the 0x1E near-miss separator."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"][:40]:
        row = _row_by_id(dossier, inst["instance_id"])
        bad = sha256_hex(bytes(row["row_payload"], "utf-8") + b"\x1e" + bytes(row["ctx_tag"], "utf-8"))
        assert row["seal_hex"] != bad
        assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])


def test_replay_digest_formula_all_closed(artifacts):
    """Every closed replay_digest must follow iid|seal|fragment."""
    dossier, transcript, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        rec = _tr_by_id(transcript, inst["instance_id"])
        assert rec["replay_digest"] == sha256_hex(
            f"{inst['instance_id']}|{row['seal_hex']}|{row['fragment_line']}"
        )


def test_obligation_ids_full_on_clean_rows(artifacts):
    """Clean closed rows must list the full OBL-11 family."""
    _d, transcript, closed = artifacts
    want = ["OBL-11", "OBL-11a", "OBL-11b", "OBL-11c"]
    for inst in closed["instances"]:
        rec = _tr_by_id(transcript, inst["instance_id"])
        assert rec["obligation_ids_satisfied"] == want


def test_verify_clean_true(artifacts):
    """Successful fuzz probe must leave verify_clean set."""
    _d, transcript, _c = artifacts
    assert transcript["verify_clean"] is True


def test_pairing_left_offset_three_not_five(artifacts):
    """Left offset must be +3; swapped +5 left must not match."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        if inst["left"] == inst["right"]:
            continue
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["slot_score"] != swapped_slot(inst["left"], inst["right"])


def test_gap_a_gap_b_coherence_all(artifacts):
    """Corpus gap fields must remain coherent with pairing-derived boosted."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["boosted_score"] == expected_gap(inst["gap_a"], inst["gap_b"], inst["nest_depth"])


def test_metamorphic_slot_shift_left(artifacts):
    """Incrementing left index must change slot unless modular collision."""
    dossier, _t, closed = artifacts
    changed = 0
    for inst in closed["instances"]:
        # verify formula stability metamorphic: f(L)+diff
        row = _row_by_id(dossier, inst["instance_id"])
        alt = expected_slot(inst["left"] + 1, inst["right"])
        if alt != row["slot_score"]:
            changed += 1
        assert row["slot_score"] == expected_slot(inst["left"], inst["right"])
    assert changed >= 50


def test_metamorphic_boost_increment(artifacts):
    """boosted_score must equal schedule shift of slot for every closed row."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["boosted_score"] == (row["slot_score"] + inst["nest_depth"] * 7 + inst["boost"]) % 97


def test_suite_coverage_minimums(artifacts):
    """Each suite label must cover a non-trivial closed subset."""
    _d, _t, closed = artifacts
    from collections import Counter

    c = Counter(i["suite"] for i in closed["instances"])
    for s in ("suite_a", "suite_b", "suite_c"):
        assert c[s] >= 40


def test_ns7_and_ns9_both_present(artifacts):
    """Both ns7 and ns9 graphs must appear in closed corpora and dossier."""
    dossier, _t, closed = artifacts
    graphs = {i["graph"] for i in closed["instances"]}
    assert graphs >= {"ns7", "ns9"}
    dgraphs = {r["graph"] for r in dossier["dossier_rows"]}
    assert "ns7" in dgraphs and "ns9" in dgraphs


def test_perm_stress_orders_unique(artifacts):
    """Permutation stress orders must not be identical copies."""
    _d, _t, _c = artifacts
    orders = [tuple(json.loads(line)["order"]) for line in PERM.read_text().splitlines() if line.strip()]
    assert len(orders) >= 5
    assert len(set(orders)) >= 2


def test_journal_shard_instance_ids_subset_of_dossier(artifacts):
    """Current-epoch journal instance ids must be a subset of dossier ids."""
    _d, _t, _c = artifacts
    run_emit_verify()
    dossier = json.loads(DOSSIER.read_text())
    epoch = dossier["journal_epoch"]
    dossier_ids = {r["instance_id"] for r in dossier["dossier_rows"]}
    for name in ("suite_a.jsonl", "suite_b.jsonl", "suite_c.jsonl", "arm_omit.jsonl"):
        for line in _load_shard(name):
            if line.get("epoch") == epoch:
                assert line["instance_id"] in dossier_ids


def test_journal_preserves_seal_hex(artifacts):
    """Journal lines must retain the same seal_hex as the merged dossier row."""
    _d, _t, _c = artifacts
    run_emit_verify()
    dossier = json.loads(DOSSIER.read_text())
    epoch = dossier["journal_epoch"]
    by_id = {r["instance_id"]: r for r in dossier["dossier_rows"]}
    for name in ("suite_a.jsonl", "suite_b.jsonl", "suite_c.jsonl", "arm_omit.jsonl"):
        for line in _load_shard(name):
            if line.get("epoch") != epoch:
                continue
            row = by_id[line["instance_id"]]
            assert line["seal_hex"] == row["seal_hex"]


def test_journal_preserves_fragment(artifacts):
    """Journal lines must retain fragment_line through merge."""
    _d, _t, _c = artifacts
    run_emit_verify()
    dossier = json.loads(DOSSIER.read_text())
    epoch = dossier["journal_epoch"]
    by_id = {r["instance_id"]: r for r in dossier["dossier_rows"]}
    for name in ("suite_a.jsonl", "suite_b.jsonl", "suite_c.jsonl", "arm_omit.jsonl"):
        for line in _load_shard(name):
            if line.get("epoch") != epoch:
                continue
            assert line["fragment_line"] == by_id[line["instance_id"]]["fragment_line"]


def test_arm_omit_boosted_matches_pairing(artifacts):
    """Arm-omit boosted scores must match the full pairing+shift formula."""
    dossier, _t, _c = artifacts
    for ao in _arm_cases():
        row = _row_by_id(dossier, ao["case_id"])
        assert row["boosted_score"] == expected_boosted(
            ao["left"], ao["right"], ao["nest_depth"], ao["boost"]
        )


def test_arm_omit_seal_matches_formula(artifacts):
    """Arm-omit seals must match annex material hashing."""
    dossier, _t, _c = artifacts
    for ao in _arm_cases():
        row = _row_by_id(dossier, ao["case_id"])
        assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])


def test_no_duplicate_seals_forced_collision(artifacts):
    """Distinct payloads must not collapse to one seal under a shared ctx."""
    dossier, _t, closed = artifacts
    from collections import defaultdict

    by_ctx = defaultdict(list)
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        by_ctx[row["ctx_tag"]].append(row["row_payload"] + "||" + row["seal_hex"])
    for items in by_ctx.values():
        payloads = {x.split("||", 1)[0] for x in items}
        seals = {x.split("||", 1)[1] for x in items}
        assert len(seals) >= min(len(payloads), len(seals))


def test_slot_rejects_sum_pairing_closed(artifacts):
    """Closed rows must reject additive near-miss pairing."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        if sum_slot(inst["left"], inst["right"]) != expected_slot(inst["left"], inst["right"]):
            assert row["slot_score"] != sum_slot(inst["left"], inst["right"])


def test_boosted_rejects_doubled_boost_closed(artifacts):
    """Closed boosted must reject boost*2 near-miss shift."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        if inst["boost"] == 0:
            continue
        row = _row_by_id(dossier, inst["instance_id"])
        doubled = (expected_slot(inst["left"], inst["right"]) + inst["nest_depth"] * 7 + inst["boost"] * 2) % 97
        if doubled != expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"]):
            assert row["boosted_score"] != doubled


def test_fragment_pipe_field_count_all(artifacts):
    """Every fragment_line must contain exactly three pipe-separated fields."""
    dossier, _t, _c = artifacts
    for row in dossier["dossier_rows"]:
        assert len(row["fragment_line"].split("|")) == 3


def test_payload_three_pipe_fields_all(artifacts):
    """Every row_payload must be iid|boosted|fragment with fragment kept intact."""
    dossier, _t, _c = artifacts
    for row in dossier["dossier_rows"]:
        parts = row["row_payload"].split("|", 2)
        assert len(parts) == 3
        assert parts[0] == row["instance_id"]
        assert parts[1] == str(row["boosted_score"])
        assert parts[2] == row["fragment_line"]


def test_margin2_zero_requires_seal_and_fragment(artifacts):
    """margin_2 stays zero only when fragment and seal both match annex."""
    dossier, transcript, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        rec = _tr_by_id(transcript, inst["instance_id"])
        assert row["fragment_line"] == expected_fragment(inst["graph"], inst["nest_depth"])
        assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])
        assert rec["fuzz_margin_vector"][2] == 0.0


def test_closed_minimum_one_eighty(artifacts):
    """Closed corpus must stay at the hardened operational scale."""
    _d, _t, closed = artifacts
    assert len(closed["instances"]) >= 180


def test_arm_omit_minimum_forty(artifacts):
    """Arm-omit corpus must stay at the hardened operational scale."""
    _d, _t, _c = artifacts
    assert len(_arm_cases()) >= 40


def test_diversity_left_span(artifacts):
    """Closed left indices must span a wide numeric range."""
    _d, _t, closed = artifacts
    lefts = [i["left"] for i in closed["instances"]]
    assert max(lefts) - min(lefts) >= 40


def test_diversity_right_span(artifacts):
    """Closed right indices must span a wide numeric range."""
    _d, _t, closed = artifacts
    rights = [i["right"] for i in closed["instances"]]
    assert max(rights) - min(rights) >= 40


def test_diversity_depth_includes_zero_and_deep(artifacts):
    """Nest depths must include both zero and depths above eight."""
    _d, _t, closed = artifacts
    depths = {i["nest_depth"] for i in closed["instances"]}
    assert 0 in depths
    assert any(d > 8 for d in depths)


def test_diversity_boost_includes_zero_and_large(artifacts):
    """Boost values must include zero and values at or above twenty."""
    _d, _t, closed = artifacts
    boosts = {i["boost"] for i in closed["instances"]}
    assert 0 in boosts
    assert any(b >= 20 for b in boosts)


def test_shard_manifest_order_stable(artifacts):
    """shard_manifest order must match the annex list order."""
    dossier, _t, _c = artifacts
    annex = (APP / "annex" / "margin_contract.inc").read_text()
    start = annex.index('["suite_a"')
    end = annex.index("]", start) + 1
    raw = annex[start:end].replace('"', "")
    expect = [p.strip() for p in raw.strip("[]").split(",")]
    assert list(dossier["shard_manifest"]) == expect


def test_obligation_coverage_top_level(artifacts):
    """Dossier obligation_coverage must include the OBL-11 family."""
    dossier, _t, _c = artifacts
    cov = set(dossier["obligation_coverage"])
    for oid in ("OBL-11", "OBL-11a", "OBL-11b", "OBL-11c"):
        assert oid in cov


def test_transcript_instance_count_matches_closed(artifacts):
    """Transcript instances must cover exactly the closed corpus."""
    _d, transcript, closed = artifacts
    assert len(transcript["instances"]) == len(closed["instances"])


def test_fuzz_vector_all_zero_closed(artifacts):
    """Every closed fuzz vector must be the zero triple."""
    _d, transcript, closed = artifacts
    for inst in closed["instances"]:
        rec = _tr_by_id(transcript, inst["instance_id"])
        assert rec["fuzz_margin_vector"] == [0.0, 0.0, 0.0]


def test_seal_hex_lowercase(artifacts):
    """seal_hex values must be lowercase hex."""
    dossier, _t, _c = artifacts
    for row in dossier["dossier_rows"]:
        assert row["seal_hex"] == row["seal_hex"].lower()
        int(row["seal_hex"], 16)


def test_recovery_changes_if_replay_perm_would(artifacts):
    """recovery_digest must differ from hashing replay digests in dossier row order when unsorted."""
    dossier, transcript, closed = artifacts
    # build replays in dossier row order for closed only
    closed_ids = {i["instance_id"] for i in closed["instances"]}
    ordered = []
    for row in dossier["dossier_rows"]:
        if row["instance_id"] in closed_ids:
            rec = _tr_by_id(transcript, row["instance_id"])
            ordered.append(rec["replay_digest"])
    sorted_replays = sorted(ordered)
    if ordered != sorted_replays:
        assert transcript["recovery_digest"] != sha256_hex(json.dumps(ordered, separators=(",", ":")))
    assert transcript["recovery_digest"] == sha256_hex(json.dumps(sorted_replays, separators=(",", ":")))


def test_equal_index_slot_matches_product(artifacts):
    """Equal-index rows must match the product formula exactly."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        if inst["left"] != inst["right"]:
            continue
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["slot_score"] == ((inst["left"] + 3) * (inst["right"] + 5) + 19) % 97


def test_wrap_slot_near_modulus(artifacts):
    """High product pairing must wrap through mod 97 without post-clamp."""
    dossier, _t, closed = artifacts
    hits = 0
    for inst in closed["instances"]:
        raw = (inst["left"] + 3) * (inst["right"] + 5) + 19
        if raw % 97 > 90:
            row = _row_by_id(dossier, inst["instance_id"])
            assert row["slot_score"] == raw % 97
            hits += 1
    assert hits >= 1


def test_arm_omit_ctx_tag_form(artifacts):
    """Arm-omit ctx_tag must follow graph:depth."""
    dossier, _t, _c = artifacts
    for ao in _arm_cases():
        row = _row_by_id(dossier, ao["case_id"])
        assert row["ctx_tag"] == expected_ctx(ao["graph"], ao["nest_depth"])


def test_arm_omit_payload_embeds_case_id(artifacts):
    """Arm-omit payloads must start with case_id."""
    dossier, _t, _c = artifacts
    for ao in _arm_cases():
        row = _row_by_id(dossier, ao["case_id"])
        assert row["row_payload"].startswith(ao["case_id"] + "|")


def test_closed_no_arm_omit_id_overlap(artifacts):
    """Closed instance ids and arm-omit case ids must be disjoint."""
    _d, _t, closed = artifacts
    cids = {i["instance_id"] for i in closed["instances"]}
    aids = {a["case_id"] for a in _arm_cases()}
    assert not (cids & aids)


def test_journal_stamp_file_numeric(artifacts):
    """epoch.stamp must contain a decimal integer watermark."""
    _d, _t, _c = artifacts
    text = STAMP.read_text().strip()
    int(text)
    assert text == str(int(text))


def test_second_emit_rewrites_shards(artifacts):
    """A second emit must append a new epoch while dossier uses only that epoch."""
    _d, _t, _c = artifacts
    e_before = int(STAMP.read_text().strip())
    run_emit_verify()
    d2 = json.loads(DOSSIER.read_text())
    assert d2["journal_epoch"] == e_before + 1
    epochs = set()
    for name in ("suite_a.jsonl", "suite_b.jsonl", "suite_c.jsonl", "arm_omit.jsonl"):
        epochs |= {line.get("epoch") for line in _load_shard(name)}
    assert d2["journal_epoch"] in epochs
    assert len(epochs) >= 2
    # Dossier content must still be formula-correct for the new epoch.
    for row in d2["dossier_rows"]:
        assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])


def test_boosted_not_equal_gap_substitute_with_wrong_slot(artifacts):
    """Coherent boosted alone is insufficient: slot_score must also match pairing."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["slot_score"] == expected_slot(inst["left"], inst["right"])
        assert row["boosted_score"] == expected_boosted(
            inst["left"], inst["right"], inst["nest_depth"], inst["boost"]
        )


def test_fragment_continuity_matches_fnv(artifacts):
    """C:N continuity digits must equal (fnv(graph)+depth*13) mod 1e5."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        cont = (fnv1a32(inst["graph"]) + inst["nest_depth"] * 13) % 100000
        parts = row["fragment_line"].split("|")
        assert parts[-1] == f"C:N{cont}"


def test_trace_span_not_concat_hash(artifacts):
    """trace_span_digest must not equal sha256 of bare seal concatenation."""
    dossier, _t, _c = artifacts
    seals = sorted(r["seal_hex"] for r in dossier["dossier_rows"])
    concat = sha256_hex("".join(seals))
    assert dossier["trace_span_digest"] != concat


def test_recovery_not_trace_span(artifacts):
    """recovery_digest must differ from trace_span_digest."""
    dossier, transcript, _c = artifacts
    assert transcript["recovery_digest"] != dossier["trace_span_digest"]


def test_nest_depth_nonnegative(artifacts):
    """All nest_depth values on dossier rows must be non-negative."""
    dossier, _t, _c = artifacts
    for row in dossier["dossier_rows"]:
        assert row["nest_depth"] >= 0


def test_graph_echo_arm_omit(artifacts):
    """Arm-omit rows must echo their corpus graph id."""
    dossier, _t, _c = artifacts
    for ao in _arm_cases():
        row = _row_by_id(dossier, ao["case_id"])
        assert row["graph"] == ao["graph"]


def test_nest_depth_echo_arm_omit(artifacts):
    """Arm-omit rows must echo nest_depth."""
    dossier, _t, _c = artifacts
    for ao in _arm_cases():
        row = _row_by_id(dossier, ao["case_id"])
        assert row["nest_depth"] == ao["nest_depth"]


def test_slot_score_arm_omit_product(artifacts):
    """Arm-omit slot_score must use product pairing offsets."""
    dossier, _t, _c = artifacts
    for ao in _arm_cases():
        row = _row_by_id(dossier, ao["case_id"])
        assert row["slot_score"] == expected_slot(ao["left"], ao["right"])
        if ao["left"] != ao["right"]:
            assert row["slot_score"] != swapped_slot(ao["left"], ao["right"])


def test_many_asymmetric_pairs_present(artifacts):
    """Hardened corpora must keep a large asymmetric pairing set."""
    _d, _t, closed = artifacts
    asym = [i for i in closed["instances"] if i["left"] != i["right"]]
    assert len(asym) >= 100


def test_many_equal_pairs_present(artifacts):
    """Hardened corpora must include multiple equal-index pairs."""
    _d, _t, closed = artifacts
    eq = [i for i in closed["instances"] if i["left"] == i["right"]]
    assert len(eq) >= 5


def test_replay_digest_length_64_all(artifacts):
    """Every replay_digest must be 64 lowercase hex chars."""
    _d, transcript, closed = artifacts
    for inst in closed["instances"]:
        rec = _tr_by_id(transcript, inst["instance_id"])
        assert len(rec["replay_digest"]) == 64


def test_dossier_rows_are_objects(artifacts):
    """dossier_rows must be a non-empty list of objects with required keys."""
    dossier, _t, _c = artifacts
    required = {
        "instance_id",
        "graph",
        "nest_depth",
        "slot_score",
        "boosted_score",
        "fragment_line",
        "row_payload",
        "ctx_tag",
        "seal_hex",
        "edge_arms",
    }
    assert len(dossier["dossier_rows"]) >= 200
    for row in dossier["dossier_rows"]:
        assert required <= set(row.keys())


def test_schedule_boost_constant_seven(artifacts):
    """Depth shift coefficient must be 7, not 5 or 11."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        alt5 = (row["slot_score"] + inst["nest_depth"] * 5 + inst["boost"]) % 97
        alt11 = (row["slot_score"] + inst["nest_depth"] * 11 + inst["boost"]) % 97
        want = (row["slot_score"] + inst["nest_depth"] * 7 + inst["boost"]) % 97
        assert row["boosted_score"] == want
        if alt5 != want:
            assert row["boosted_score"] != alt5
        if alt11 != want:
            assert row["boosted_score"] != alt11


def test_pairing_constant_nineteen_family(artifacts):
    """Pairing additive constant must be 19 across a broad sample."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"][::3]:
        row = _row_by_id(dossier, inst["instance_id"])
        wrong17 = ((inst["left"] + 3) * (inst["right"] + 5) + 17) % 97
        if wrong17 != expected_slot(inst["left"], inst["right"]):
            assert row["slot_score"] != wrong17


def test_mod_prime_remains_ninety_seven(artifacts):
    """Scores must use modulus 97, not 89 or 101."""
    dossier, _t, closed = artifacts
    discriminated = 0
    for inst in closed["instances"][::2]:
        row = _row_by_id(dossier, inst["instance_id"])
        raw = (inst["left"] + 3) * (inst["right"] + 5) + 19
        assert row["slot_score"] == raw % 97
        if raw % 89 != raw % 97:
            assert row["slot_score"] != raw % 89
            discriminated += 1
        if raw % 101 != raw % 97:
            assert row["slot_score"] != raw % 101
    assert discriminated >= 20


def test_arm_omit_not_in_suite_shards(artifacts):
    """Arm-omit case ids must not be filed into suite_*.jsonl shards."""
    _d, _t, _c = artifacts
    run_emit_verify()
    dossier = json.loads(DOSSIER.read_text())
    epoch = dossier["journal_epoch"]
    ao_ids = {a["case_id"] for a in _arm_cases()}
    for suite in ("suite_a", "suite_b", "suite_c"):
        for line in _load_shard(f"{suite}.jsonl"):
            if line.get("epoch") == epoch:
                assert line["instance_id"] not in ao_ids


def test_closed_not_in_arm_omit_shard(artifacts):
    """Closed instance ids must not be filed into arm_omit.jsonl."""
    _d, _t, closed = artifacts
    run_emit_verify()
    dossier = json.loads(DOSSIER.read_text())
    epoch = dossier["journal_epoch"]
    cids = {i["instance_id"] for i in closed["instances"]}
    for line in _load_shard("arm_omit.jsonl"):
        if line.get("epoch") == epoch:
            assert line["instance_id"] not in cids


def test_suite_routing_matches_corpus(artifacts):
    """Closed rows must land in the journal shard named by their suite label."""
    _d, _t, closed = artifacts
    run_emit_verify()
    dossier = json.loads(DOSSIER.read_text())
    epoch = dossier["journal_epoch"]
    for inst in closed["instances"]:
        lines = [
            x
            for x in _load_shard(f"{inst['suite']}.jsonl")
            if x.get("epoch") == epoch and x.get("instance_id") == inst["instance_id"]
        ]
        assert len(lines) == 1


def test_triple_emit_idempotent_semantics(artifacts):
    """Three emit cycles must keep seals and boosted scores stable."""
    d0, _t, closed = artifacts
    run_emit_verify()
    run_emit_verify()
    d2 = json.loads(DOSSIER.read_text())
    for inst in closed["instances"]:
        r0 = _row_by_id(d0, inst["instance_id"])
        r2 = _row_by_id(d2, inst["instance_id"])
        assert r0["seal_hex"] == r2["seal_hex"]
        assert r0["boosted_score"] == r2["boosted_score"]
        assert r0["fragment_line"] == r2["fragment_line"]


def test_recovery_digest_stable_across_triple_emit(artifacts):
    """recovery_digest must remain stable across three emit/verify cycles."""
    _d, t0, _c = artifacts
    run_emit_verify()
    run_emit_verify()
    t2 = json.loads(TRANSCRIPT.read_text())
    assert t0["recovery_digest"] == t2["recovery_digest"]


def test_margin_vector_types_are_floats(artifacts):
    """Fuzz margin components must be JSON numbers (floats)."""
    _d, transcript, closed = artifacts
    for inst in closed["instances"]:
        rec = _tr_by_id(transcript, inst["instance_id"])
        for v in rec["fuzz_margin_vector"]:
            assert isinstance(v, (int, float))


def test_payload_middle_field_is_boosted_not_slot(artifacts):
    """Payload middle field must embed boosted_score, not slot_score."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        mid = row["row_payload"].split("|")[1]
        assert mid == str(row["boosted_score"])
        if row["slot_score"] != row["boosted_score"]:
            assert mid != str(row["slot_score"])


def test_shared_graph_depth_same_fragment(artifacts):
    """Identical graph/depth pairs must share one fragment_line."""
    dossier, _t, closed = artifacts
    from collections import defaultdict

    groups = defaultdict(set)
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        groups[(inst["graph"], inst["nest_depth"])].add(row["fragment_line"])
    for frags in groups.values():
        assert len(frags) == 1


def test_different_depth_different_fragment(artifacts):
    """Different depths on the same graph must yield different fragments."""
    dossier, _t, closed = artifacts
    from collections import defaultdict

    by_graph = defaultdict(dict)
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        by_graph[inst["graph"]][inst["nest_depth"]] = row["fragment_line"]
    for depth_map in by_graph.values():
        if len(depth_map) >= 2:
            assert len(set(depth_map.values())) == len(depth_map)


def test_zero_left_nonzero_right_sample(artifacts):
    """Rows with left=0 and nonzero right must follow product pairing."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if i["left"] == 0 and i["right"] != 0]
    assert len(hits) >= 1
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["slot_score"] == expected_slot(0, inst["right"])


def test_nonzero_left_zero_right_sample(artifacts):
    """Rows with nonzero left and right=0 must follow product pairing."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if i["left"] != 0 and i["right"] == 0]
    assert len(hits) >= 1
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["slot_score"] == expected_slot(inst["left"], 0)


def test_arm_omit_scale_forty(artifacts):
    """Arm-omit operational scale after hardening."""
    _d, _t, _c = artifacts
    assert len(_arm_cases()) >= 40


def test_closed_scale_one_eighty(artifacts):
    """Closed operational scale after hardening."""
    _d, _t, closed = artifacts
    assert len(closed["instances"]) >= 180


def test_journal_epoch_positive_after_second_emit(artifacts):
    """journal_epoch stays positive and increases after another emit."""
    d1, _t, _c = artifacts
    run_emit_verify()
    d2 = json.loads(DOSSIER.read_text())
    assert d1["journal_epoch"] >= 1
    assert d2["journal_epoch"] > d1["journal_epoch"]


def test_edge_arms_type_list(artifacts):
    """edge_arms must be a JSON array on every row."""
    dossier, _t, _c = artifacts
    for row in dossier["dossier_rows"]:
        assert isinstance(row["edge_arms"], list)
        assert len(row["edge_arms"]) >= 2


def test_seal_deterministic_formula_arm_omit(artifacts):
    """Arm-omit seals must be deterministic under the annex formula."""
    dossier, _t, _c = artifacts
    for ao in _arm_cases():
        row = _row_by_id(dossier, ao["case_id"])
        assert row["seal_hex"] == expected_seal(
            expected_payload(ao["case_id"], row["boosted_score"], row["fragment_line"]),
            expected_ctx(ao["graph"], ao["nest_depth"]),
        )


def test_fragment_ns7_continuity_sample(artifacts):
    """ns7 fragments must match annex continuity on a broad sample."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if i["graph"] == "ns7"]
    assert len(hits) >= 50
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["fragment_line"] == expected_fragment("ns7", inst["nest_depth"])


def test_fragment_ns9_continuity_sample(artifacts):
    """ns9 fragments must match annex continuity on a broad sample."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if i["graph"] == "ns9"]
    assert len(hits) >= 50
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["fragment_line"] == expected_fragment("ns9", inst["nest_depth"])


def test_boosted_shift_independent_of_gap_fields(artifacts):
    """boosted_score must be computable from left/right/depth/boost alone."""
    dossier, _t, closed = artifacts
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["boosted_score"] == expected_boosted(
            inst["left"], inst["right"], inst["nest_depth"], inst["boost"]
        )


def test_all_margins_clean_flag(artifacts):
    """Transcript all_margins_clean must be true when vectors are zero."""
    _d, transcript, _c = artifacts
    assert transcript.get("all_margins_clean") is True


def test_coverage_ok_flag(artifacts):
    """Transcript coverage_ok must be true when obligations are present."""
    _d, transcript, _c = artifacts
    assert transcript.get("coverage_ok") is True


def test_shard_line_has_required_row_fields(artifacts):
    """Current-epoch journal lines must carry core row fields before merge strip."""
    _d, _t, _c = artifacts
    run_emit_verify()
    dossier = json.loads(DOSSIER.read_text())
    epoch = dossier["journal_epoch"]
    needed = {"instance_id", "seal_hex", "fragment_line", "row_payload", "ctx_tag", "edge_arms", "epoch"}
    for name in ("suite_a.jsonl", "suite_b.jsonl", "suite_c.jsonl", "arm_omit.jsonl"):
        lines = [x for x in _load_shard(name) if x.get("epoch") == epoch]
        assert lines
        for line in lines:
            assert needed <= set(line.keys())


def test_no_epoch_field_on_public_rows(artifacts):
    """Public dossier_rows must not leak the journal epoch field."""
    dossier, _t, _c = artifacts
    for row in dossier["dossier_rows"]:
        assert "epoch" not in row


def test_no_suite_field_on_public_rows(artifacts):
    """Public dossier_rows must not leak routing-only suite labels."""
    dossier, _t, _c = artifacts
    for row in dossier["dossier_rows"]:
        assert "suite" not in row


def test_high_depth_boost_combo_sample(artifacts):
    """Rows with deep nest and nonzero boost must wrap correctly."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if i["nest_depth"] >= 10 and i["boost"] > 0]
    assert len(hits) >= 3
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["boosted_score"] == expected_boosted(
            inst["left"], inst["right"], inst["nest_depth"], inst["boost"]
        )


def test_perm_orders_length_matches_closed(artifacts):
    """Each permutation order length must equal closed corpus size."""
    _d, _t, closed = artifacts
    n = len(closed["instances"])
    for line in PERM.read_text().splitlines():
        if not line.strip():
            continue
        assert len(json.loads(line)["order"]) == n


def test_instance_id_stable_string(artifacts):
    """instance_id values must be non-empty strings."""
    dossier, _t, _c = artifacts
    for row in dossier["dossier_rows"]:
        assert isinstance(row["instance_id"], str)
        assert len(row["instance_id"]) >= 2


def test_seal_changes_when_fragment_changes(artifacts):
    """Different fragments under related rows must not force identical seals."""
    dossier, _t, closed = artifacts
    rows = [_row_by_id(dossier, i["instance_id"]) for i in closed["instances"][:30]]
    frags = {r["fragment_line"] for r in rows}
    if len(frags) > 1:
        seals = {r["seal_hex"] for r in rows}
        assert len(seals) > 1


def test_arm_omit_replay_not_required(artifacts):
    """Transcript covers closed instances only; arm-omit is dossier-side coverage."""
    _d, transcript, closed = artifacts
    tids = {r["instance_id"] for r in transcript["instances"]}
    assert tids == {i["instance_id"] for i in closed["instances"]}
    for ao in _arm_cases():
        assert ao["case_id"] not in tids


def test_dossier_arm_omit_count(artifacts):
    """Dossier must contain exactly the arm-omit corpus count of ao rows."""
    dossier, _t, _c = artifacts
    ao_ids = {a["case_id"] for a in _arm_cases()}
    got = [r for r in dossier["dossier_rows"] if r["instance_id"] in ao_ids]
    assert len(got) == len(ao_ids)


def test_boost_zero_depth_nonzero(artifacts):
    """boost=0 with nonzero depth must still apply the depth*7 term."""
    dossier, _t, closed = artifacts
    hits = [i for i in closed["instances"] if i["boost"] == 0 and i["nest_depth"] > 0]
    assert len(hits) >= 10
    for inst in hits:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["boosted_score"] == (row["slot_score"] + inst["nest_depth"] * 7) % 97


def test_json_dump_separators_for_trace(artifacts):
    """trace_span_digest must use compact JSON array encoding."""
    dossier, _t, _c = artifacts
    seals = sorted(r["seal_hex"] for r in dossier["dossier_rows"])
    compact = json.dumps(seals, separators=(",", ":"))
    pretty = json.dumps(seals, indent=2)
    assert dossier["trace_span_digest"] == sha256_hex(compact)
    if pretty != compact:
        assert dossier["trace_span_digest"] != sha256_hex(pretty)


def test_closed_row_formula_sample_0(artifacts):
    """Sample closed row 0 must satisfy slot, boost, fragment, seal, payload."""
    dossier, _t, closed = artifacts
    inst = closed["instances"][0]
    row = _row_by_id(dossier, inst["instance_id"])
    assert row["slot_score"] == expected_slot(inst["left"], inst["right"])
    assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
    assert row["fragment_line"] == expected_fragment(inst["graph"], inst["nest_depth"])
    assert row["row_payload"] == expected_payload(inst["instance_id"], row["boosted_score"], row["fragment_line"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])


def test_closed_row_formula_sample_1(artifacts):
    """Sample closed row 1 must satisfy slot, boost, fragment, seal, payload."""
    dossier, _t, closed = artifacts
    inst = closed["instances"][1]
    row = _row_by_id(dossier, inst["instance_id"])
    assert row["slot_score"] == expected_slot(inst["left"], inst["right"])
    assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
    assert row["fragment_line"] == expected_fragment(inst["graph"], inst["nest_depth"])
    assert row["row_payload"] == expected_payload(inst["instance_id"], row["boosted_score"], row["fragment_line"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])


def test_closed_row_formula_sample_2(artifacts):
    """Sample closed row 2 must satisfy slot, boost, fragment, seal, payload."""
    dossier, _t, closed = artifacts
    inst = closed["instances"][2]
    row = _row_by_id(dossier, inst["instance_id"])
    assert row["slot_score"] == expected_slot(inst["left"], inst["right"])
    assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
    assert row["fragment_line"] == expected_fragment(inst["graph"], inst["nest_depth"])
    assert row["row_payload"] == expected_payload(inst["instance_id"], row["boosted_score"], row["fragment_line"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])


def test_closed_row_formula_sample_3(artifacts):
    """Sample closed row 3 must satisfy slot, boost, fragment, seal, payload."""
    dossier, _t, closed = artifacts
    inst = closed["instances"][3]
    row = _row_by_id(dossier, inst["instance_id"])
    assert row["slot_score"] == expected_slot(inst["left"], inst["right"])
    assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
    assert row["fragment_line"] == expected_fragment(inst["graph"], inst["nest_depth"])
    assert row["row_payload"] == expected_payload(inst["instance_id"], row["boosted_score"], row["fragment_line"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])


def test_closed_row_formula_sample_4(artifacts):
    """Sample closed row 4 must satisfy slot, boost, fragment, seal, payload."""
    dossier, _t, closed = artifacts
    inst = closed["instances"][4]
    row = _row_by_id(dossier, inst["instance_id"])
    assert row["slot_score"] == expected_slot(inst["left"], inst["right"])
    assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
    assert row["fragment_line"] == expected_fragment(inst["graph"], inst["nest_depth"])
    assert row["row_payload"] == expected_payload(inst["instance_id"], row["boosted_score"], row["fragment_line"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])


def test_closed_row_formula_sample_5(artifacts):
    """Sample closed row 5 must satisfy slot, boost, fragment, seal, payload."""
    dossier, _t, closed = artifacts
    inst = closed["instances"][5]
    row = _row_by_id(dossier, inst["instance_id"])
    assert row["slot_score"] == expected_slot(inst["left"], inst["right"])
    assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
    assert row["fragment_line"] == expected_fragment(inst["graph"], inst["nest_depth"])
    assert row["row_payload"] == expected_payload(inst["instance_id"], row["boosted_score"], row["fragment_line"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])


def test_closed_row_formula_sample_6(artifacts):
    """Sample closed row 6 must satisfy slot, boost, fragment, seal, payload."""
    dossier, _t, closed = artifacts
    inst = closed["instances"][6]
    row = _row_by_id(dossier, inst["instance_id"])
    assert row["slot_score"] == expected_slot(inst["left"], inst["right"])
    assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
    assert row["fragment_line"] == expected_fragment(inst["graph"], inst["nest_depth"])
    assert row["row_payload"] == expected_payload(inst["instance_id"], row["boosted_score"], row["fragment_line"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])


def test_closed_row_formula_sample_7(artifacts):
    """Sample closed row 7 must satisfy slot, boost, fragment, seal, payload."""
    dossier, _t, closed = artifacts
    inst = closed["instances"][7]
    row = _row_by_id(dossier, inst["instance_id"])
    assert row["slot_score"] == expected_slot(inst["left"], inst["right"])
    assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
    assert row["fragment_line"] == expected_fragment(inst["graph"], inst["nest_depth"])
    assert row["row_payload"] == expected_payload(inst["instance_id"], row["boosted_score"], row["fragment_line"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])


def test_closed_row_formula_sample_8(artifacts):
    """Sample closed row 8 must satisfy slot, boost, fragment, seal, payload."""
    dossier, _t, closed = artifacts
    inst = closed["instances"][8]
    row = _row_by_id(dossier, inst["instance_id"])
    assert row["slot_score"] == expected_slot(inst["left"], inst["right"])
    assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
    assert row["fragment_line"] == expected_fragment(inst["graph"], inst["nest_depth"])
    assert row["row_payload"] == expected_payload(inst["instance_id"], row["boosted_score"], row["fragment_line"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])


def test_closed_row_formula_sample_9(artifacts):
    """Sample closed row 9 must satisfy slot, boost, fragment, seal, payload."""
    dossier, _t, closed = artifacts
    inst = closed["instances"][9]
    row = _row_by_id(dossier, inst["instance_id"])
    assert row["slot_score"] == expected_slot(inst["left"], inst["right"])
    assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
    assert row["fragment_line"] == expected_fragment(inst["graph"], inst["nest_depth"])
    assert row["row_payload"] == expected_payload(inst["instance_id"], row["boosted_score"], row["fragment_line"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])


def test_closed_row_formula_sample_10(artifacts):
    """Sample closed row 10 must satisfy slot, boost, fragment, seal, payload."""
    dossier, _t, closed = artifacts
    inst = closed["instances"][10]
    row = _row_by_id(dossier, inst["instance_id"])
    assert row["slot_score"] == expected_slot(inst["left"], inst["right"])
    assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
    assert row["fragment_line"] == expected_fragment(inst["graph"], inst["nest_depth"])
    assert row["row_payload"] == expected_payload(inst["instance_id"], row["boosted_score"], row["fragment_line"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])


def test_closed_row_formula_sample_11(artifacts):
    """Sample closed row 11 must satisfy slot, boost, fragment, seal, payload."""
    dossier, _t, closed = artifacts
    inst = closed["instances"][11]
    row = _row_by_id(dossier, inst["instance_id"])
    assert row["slot_score"] == expected_slot(inst["left"], inst["right"])
    assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
    assert row["fragment_line"] == expected_fragment(inst["graph"], inst["nest_depth"])
    assert row["row_payload"] == expected_payload(inst["instance_id"], row["boosted_score"], row["fragment_line"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])


def test_closed_row_formula_sample_12(artifacts):
    """Sample closed row 12 must satisfy slot, boost, fragment, seal, payload."""
    dossier, _t, closed = artifacts
    inst = closed["instances"][12]
    row = _row_by_id(dossier, inst["instance_id"])
    assert row["slot_score"] == expected_slot(inst["left"], inst["right"])
    assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
    assert row["fragment_line"] == expected_fragment(inst["graph"], inst["nest_depth"])
    assert row["row_payload"] == expected_payload(inst["instance_id"], row["boosted_score"], row["fragment_line"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])


def test_closed_row_formula_sample_13(artifacts):
    """Sample closed row 13 must satisfy slot, boost, fragment, seal, payload."""
    dossier, _t, closed = artifacts
    inst = closed["instances"][13]
    row = _row_by_id(dossier, inst["instance_id"])
    assert row["slot_score"] == expected_slot(inst["left"], inst["right"])
    assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
    assert row["fragment_line"] == expected_fragment(inst["graph"], inst["nest_depth"])
    assert row["row_payload"] == expected_payload(inst["instance_id"], row["boosted_score"], row["fragment_line"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])


def test_closed_row_formula_sample_14(artifacts):
    """Sample closed row 14 must satisfy slot, boost, fragment, seal, payload."""
    dossier, _t, closed = artifacts
    inst = closed["instances"][14]
    row = _row_by_id(dossier, inst["instance_id"])
    assert row["slot_score"] == expected_slot(inst["left"], inst["right"])
    assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
    assert row["fragment_line"] == expected_fragment(inst["graph"], inst["nest_depth"])
    assert row["row_payload"] == expected_payload(inst["instance_id"], row["boosted_score"], row["fragment_line"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])


def test_closed_row_formula_sample_15(artifacts):
    """Sample closed row 15 must satisfy slot, boost, fragment, seal, payload."""
    dossier, _t, closed = artifacts
    inst = closed["instances"][15]
    row = _row_by_id(dossier, inst["instance_id"])
    assert row["slot_score"] == expected_slot(inst["left"], inst["right"])
    assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
    assert row["fragment_line"] == expected_fragment(inst["graph"], inst["nest_depth"])
    assert row["row_payload"] == expected_payload(inst["instance_id"], row["boosted_score"], row["fragment_line"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])


def test_closed_row_formula_sample_16(artifacts):
    """Sample closed row 16 must satisfy slot, boost, fragment, seal, payload."""
    dossier, _t, closed = artifacts
    inst = closed["instances"][16]
    row = _row_by_id(dossier, inst["instance_id"])
    assert row["slot_score"] == expected_slot(inst["left"], inst["right"])
    assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
    assert row["fragment_line"] == expected_fragment(inst["graph"], inst["nest_depth"])
    assert row["row_payload"] == expected_payload(inst["instance_id"], row["boosted_score"], row["fragment_line"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])


def test_closed_row_formula_sample_17(artifacts):
    """Sample closed row 17 must satisfy slot, boost, fragment, seal, payload."""
    dossier, _t, closed = artifacts
    inst = closed["instances"][17]
    row = _row_by_id(dossier, inst["instance_id"])
    assert row["slot_score"] == expected_slot(inst["left"], inst["right"])
    assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
    assert row["fragment_line"] == expected_fragment(inst["graph"], inst["nest_depth"])
    assert row["row_payload"] == expected_payload(inst["instance_id"], row["boosted_score"], row["fragment_line"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])


def test_closed_row_formula_sample_18(artifacts):
    """Sample closed row 18 must satisfy slot, boost, fragment, seal, payload."""
    dossier, _t, closed = artifacts
    inst = closed["instances"][18]
    row = _row_by_id(dossier, inst["instance_id"])
    assert row["slot_score"] == expected_slot(inst["left"], inst["right"])
    assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
    assert row["fragment_line"] == expected_fragment(inst["graph"], inst["nest_depth"])
    assert row["row_payload"] == expected_payload(inst["instance_id"], row["boosted_score"], row["fragment_line"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])


def test_closed_row_formula_sample_19(artifacts):
    """Sample closed row 19 must satisfy slot, boost, fragment, seal, payload."""
    dossier, _t, closed = artifacts
    inst = closed["instances"][19]
    row = _row_by_id(dossier, inst["instance_id"])
    assert row["slot_score"] == expected_slot(inst["left"], inst["right"])
    assert row["boosted_score"] == expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
    assert row["fragment_line"] == expected_fragment(inst["graph"], inst["nest_depth"])
    assert row["row_payload"] == expected_payload(inst["instance_id"], row["boosted_score"], row["fragment_line"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])


def test_arm_omit_row_formula_sample_0(artifacts):
    """Sample arm-omit row 0 must satisfy pairing, fragment, seal, arms."""
    dossier, _t, _c = artifacts
    ao = _arm_cases()[0]
    row = _row_by_id(dossier, ao["case_id"])
    assert row["slot_score"] == expected_slot(ao["left"], ao["right"])
    assert row["boosted_score"] == expected_boosted(ao["left"], ao["right"], ao["nest_depth"], ao["boost"])
    assert row["fragment_line"] == expected_fragment(ao["graph"], ao["nest_depth"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])
    assert ao["omitted_arm"] in row["edge_arms"]


def test_arm_omit_row_formula_sample_1(artifacts):
    """Sample arm-omit row 1 must satisfy pairing, fragment, seal, arms."""
    dossier, _t, _c = artifacts
    ao = _arm_cases()[1]
    row = _row_by_id(dossier, ao["case_id"])
    assert row["slot_score"] == expected_slot(ao["left"], ao["right"])
    assert row["boosted_score"] == expected_boosted(ao["left"], ao["right"], ao["nest_depth"], ao["boost"])
    assert row["fragment_line"] == expected_fragment(ao["graph"], ao["nest_depth"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])
    assert ao["omitted_arm"] in row["edge_arms"]


def test_arm_omit_row_formula_sample_2(artifacts):
    """Sample arm-omit row 2 must satisfy pairing, fragment, seal, arms."""
    dossier, _t, _c = artifacts
    ao = _arm_cases()[2]
    row = _row_by_id(dossier, ao["case_id"])
    assert row["slot_score"] == expected_slot(ao["left"], ao["right"])
    assert row["boosted_score"] == expected_boosted(ao["left"], ao["right"], ao["nest_depth"], ao["boost"])
    assert row["fragment_line"] == expected_fragment(ao["graph"], ao["nest_depth"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])
    assert ao["omitted_arm"] in row["edge_arms"]


def test_arm_omit_row_formula_sample_3(artifacts):
    """Sample arm-omit row 3 must satisfy pairing, fragment, seal, arms."""
    dossier, _t, _c = artifacts
    ao = _arm_cases()[3]
    row = _row_by_id(dossier, ao["case_id"])
    assert row["slot_score"] == expected_slot(ao["left"], ao["right"])
    assert row["boosted_score"] == expected_boosted(ao["left"], ao["right"], ao["nest_depth"], ao["boost"])
    assert row["fragment_line"] == expected_fragment(ao["graph"], ao["nest_depth"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])
    assert ao["omitted_arm"] in row["edge_arms"]


def test_arm_omit_row_formula_sample_4(artifacts):
    """Sample arm-omit row 4 must satisfy pairing, fragment, seal, arms."""
    dossier, _t, _c = artifacts
    ao = _arm_cases()[4]
    row = _row_by_id(dossier, ao["case_id"])
    assert row["slot_score"] == expected_slot(ao["left"], ao["right"])
    assert row["boosted_score"] == expected_boosted(ao["left"], ao["right"], ao["nest_depth"], ao["boost"])
    assert row["fragment_line"] == expected_fragment(ao["graph"], ao["nest_depth"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])
    assert ao["omitted_arm"] in row["edge_arms"]


def test_arm_omit_row_formula_sample_5(artifacts):
    """Sample arm-omit row 5 must satisfy pairing, fragment, seal, arms."""
    dossier, _t, _c = artifacts
    ao = _arm_cases()[5]
    row = _row_by_id(dossier, ao["case_id"])
    assert row["slot_score"] == expected_slot(ao["left"], ao["right"])
    assert row["boosted_score"] == expected_boosted(ao["left"], ao["right"], ao["nest_depth"], ao["boost"])
    assert row["fragment_line"] == expected_fragment(ao["graph"], ao["nest_depth"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])
    assert ao["omitted_arm"] in row["edge_arms"]


def test_arm_omit_row_formula_sample_6(artifacts):
    """Sample arm-omit row 6 must satisfy pairing, fragment, seal, arms."""
    dossier, _t, _c = artifacts
    ao = _arm_cases()[6]
    row = _row_by_id(dossier, ao["case_id"])
    assert row["slot_score"] == expected_slot(ao["left"], ao["right"])
    assert row["boosted_score"] == expected_boosted(ao["left"], ao["right"], ao["nest_depth"], ao["boost"])
    assert row["fragment_line"] == expected_fragment(ao["graph"], ao["nest_depth"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])
    assert ao["omitted_arm"] in row["edge_arms"]


def test_arm_omit_row_formula_sample_7(artifacts):
    """Sample arm-omit row 7 must satisfy pairing, fragment, seal, arms."""
    dossier, _t, _c = artifacts
    ao = _arm_cases()[7]
    row = _row_by_id(dossier, ao["case_id"])
    assert row["slot_score"] == expected_slot(ao["left"], ao["right"])
    assert row["boosted_score"] == expected_boosted(ao["left"], ao["right"], ao["nest_depth"], ao["boost"])
    assert row["fragment_line"] == expected_fragment(ao["graph"], ao["nest_depth"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])
    assert ao["omitted_arm"] in row["edge_arms"]


def test_arm_omit_row_formula_sample_8(artifacts):
    """Sample arm-omit row 8 must satisfy pairing, fragment, seal, arms."""
    dossier, _t, _c = artifacts
    ao = _arm_cases()[8]
    row = _row_by_id(dossier, ao["case_id"])
    assert row["slot_score"] == expected_slot(ao["left"], ao["right"])
    assert row["boosted_score"] == expected_boosted(ao["left"], ao["right"], ao["nest_depth"], ao["boost"])
    assert row["fragment_line"] == expected_fragment(ao["graph"], ao["nest_depth"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])
    assert ao["omitted_arm"] in row["edge_arms"]


def test_arm_omit_row_formula_sample_9(artifacts):
    """Sample arm-omit row 9 must satisfy pairing, fragment, seal, arms."""
    dossier, _t, _c = artifacts
    ao = _arm_cases()[9]
    row = _row_by_id(dossier, ao["case_id"])
    assert row["slot_score"] == expected_slot(ao["left"], ao["right"])
    assert row["boosted_score"] == expected_boosted(ao["left"], ao["right"], ao["nest_depth"], ao["boost"])
    assert row["fragment_line"] == expected_fragment(ao["graph"], ao["nest_depth"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])
    assert ao["omitted_arm"] in row["edge_arms"]


def test_arm_omit_row_formula_sample_10(artifacts):
    """Sample arm-omit row 10 must satisfy pairing, fragment, seal, arms."""
    dossier, _t, _c = artifacts
    ao = _arm_cases()[10]
    row = _row_by_id(dossier, ao["case_id"])
    assert row["slot_score"] == expected_slot(ao["left"], ao["right"])
    assert row["boosted_score"] == expected_boosted(ao["left"], ao["right"], ao["nest_depth"], ao["boost"])
    assert row["fragment_line"] == expected_fragment(ao["graph"], ao["nest_depth"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])
    assert ao["omitted_arm"] in row["edge_arms"]


def test_arm_omit_row_formula_sample_11(artifacts):
    """Sample arm-omit row 11 must satisfy pairing, fragment, seal, arms."""
    dossier, _t, _c = artifacts
    ao = _arm_cases()[11]
    row = _row_by_id(dossier, ao["case_id"])
    assert row["slot_score"] == expected_slot(ao["left"], ao["right"])
    assert row["boosted_score"] == expected_boosted(ao["left"], ao["right"], ao["nest_depth"], ao["boost"])
    assert row["fragment_line"] == expected_fragment(ao["graph"], ao["nest_depth"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])
    assert ao["omitted_arm"] in row["edge_arms"]


def test_arm_omit_row_formula_sample_12(artifacts):
    """Sample arm-omit row 12 must satisfy pairing, fragment, seal, arms."""
    dossier, _t, _c = artifacts
    ao = _arm_cases()[12]
    row = _row_by_id(dossier, ao["case_id"])
    assert row["slot_score"] == expected_slot(ao["left"], ao["right"])
    assert row["boosted_score"] == expected_boosted(ao["left"], ao["right"], ao["nest_depth"], ao["boost"])
    assert row["fragment_line"] == expected_fragment(ao["graph"], ao["nest_depth"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])
    assert ao["omitted_arm"] in row["edge_arms"]


def test_arm_omit_row_formula_sample_13(artifacts):
    """Sample arm-omit row 13 must satisfy pairing, fragment, seal, arms."""
    dossier, _t, _c = artifacts
    ao = _arm_cases()[13]
    row = _row_by_id(dossier, ao["case_id"])
    assert row["slot_score"] == expected_slot(ao["left"], ao["right"])
    assert row["boosted_score"] == expected_boosted(ao["left"], ao["right"], ao["nest_depth"], ao["boost"])
    assert row["fragment_line"] == expected_fragment(ao["graph"], ao["nest_depth"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])
    assert ao["omitted_arm"] in row["edge_arms"]


def test_arm_omit_row_formula_sample_14(artifacts):
    """Sample arm-omit row 14 must satisfy pairing, fragment, seal, arms."""
    dossier, _t, _c = artifacts
    ao = _arm_cases()[14]
    row = _row_by_id(dossier, ao["case_id"])
    assert row["slot_score"] == expected_slot(ao["left"], ao["right"])
    assert row["boosted_score"] == expected_boosted(ao["left"], ao["right"], ao["nest_depth"], ao["boost"])
    assert row["fragment_line"] == expected_fragment(ao["graph"], ao["nest_depth"])
    assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])
    assert ao["omitted_arm"] in row["edge_arms"]


def test_durable_journal_retains_prior_epochs(artifacts):
    """After a second emit, shard files must still contain a prior epoch line."""
    d1, _t, _c = artifacts
    e1 = d1["journal_epoch"]
    run_emit_verify()
    d2 = json.loads(DOSSIER.read_text())
    e2 = d2["journal_epoch"]
    assert e2 > e1
    prior = 0
    current = 0
    for name in ("suite_a.jsonl", "suite_b.jsonl", "suite_c.jsonl", "arm_omit.jsonl"):
        for line in _load_shard(name):
            if line.get("epoch") == e1:
                prior += 1
            if line.get("epoch") == e2:
                current += 1
    assert prior >= 1
    assert current >= 1


def test_second_emit_dossier_ignores_prior_epoch(artifacts):
    """Second-emit dossier rows must match current-epoch journal seals only."""
    _d, _t, closed = artifacts
    run_emit_verify()
    dossier = json.loads(DOSSIER.read_text())
    epoch = dossier["journal_epoch"]
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row is not None
        assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])
        # Locate the journal line that fed this row: must be current epoch.
        hits = []
        for name in ("suite_a.jsonl", "suite_b.jsonl", "suite_c.jsonl", "arm_omit.jsonl"):
            for line in _load_shard(name):
                if line.get("instance_id") == inst["instance_id"] and line.get("epoch") == epoch:
                    hits.append(line)
        assert len(hits) == 1
        assert hits[0]["seal_hex"] == row["seal_hex"]


def test_prior_epoch_corruption_cannot_poison_dossier(artifacts):
    """Corrupting older journal seals must not change the next emit dossier."""
    _d, _t, closed = artifacts
    run_emit_verify()
    # Poison every on-disk journal line with a bogus seal.
    for name in ("suite_a.jsonl", "suite_b.jsonl", "suite_c.jsonl", "arm_omit.jsonl"):
        path = JOURNAL / name
        if not path.exists():
            continue
        poisoned = []
        for line in _load_shard(name):
            line = dict(line)
            line["seal_hex"] = "0" * 64
            poisoned.append(json.dumps(line, separators=(",", ":")))
        path.write_text("\n".join(poisoned) + ("\n" if poisoned else ""))
    run_emit_verify()
    dossier = json.loads(DOSSIER.read_text())
    for inst in closed["instances"][:40]:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["seal_hex"] != "0" * 64
        assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])


def test_suite_routing_not_all_in_suite_a(artifacts):
    """Closed suite_b and suite_c rows must not live only in suite_a.jsonl."""
    _d, _t, closed = artifacts
    run_emit_verify()
    dossier = json.loads(DOSSIER.read_text())
    epoch = dossier["journal_epoch"]
    suite_b_ids = {i["instance_id"] for i in closed["instances"] if i["suite"] == "suite_b"}
    suite_c_ids = {i["instance_id"] for i in closed["instances"] if i["suite"] == "suite_c"}
    b_lines = {x["instance_id"] for x in _load_shard("suite_b.jsonl") if x.get("epoch") == epoch}
    c_lines = {x["instance_id"] for x in _load_shard("suite_c.jsonl") if x.get("epoch") == epoch}
    assert suite_b_ids and suite_b_ids <= b_lines
    assert suite_c_ids and suite_c_ids <= c_lines


def test_arm_omit_not_dumped_into_suite_a(artifacts):
    """Arm-omit cases for the current epoch must not appear in suite_a.jsonl."""
    _d, _t, _c = artifacts
    run_emit_verify()
    dossier = json.loads(DOSSIER.read_text())
    epoch = dossier["journal_epoch"]
    ao_ids = {ao["case_id"] for ao in _arm_cases()}
    suite_a = {x["instance_id"] for x in _load_shard("suite_a.jsonl") if x.get("epoch") == epoch}
    assert len(ao_ids & suite_a) == 0


def test_shared_ctx_all_distinct_seals(artifacts):
    """Every distinct payload sharing a ctx_tag must keep a distinct seal_hex."""
    dossier, _t, _c = artifacts
    by_ctx = {}
    for row in dossier["dossier_rows"]:
        ctx = row["ctx_tag"]
        if ctx not in by_ctx:
            by_ctx[ctx] = []
        by_ctx[ctx].append(row)
    collided = 0
    for ctx, rows in by_ctx.items():
        if len(rows) < 2:
            continue
        collided += 1
        seals = {r["seal_hex"] for r in rows}
        payloads = {r["row_payload"] for r in rows}
        assert len(payloads) == len(rows)
        assert len(seals) == len(rows)
        for r in rows:
            assert r["seal_hex"] == expected_seal(r["row_payload"], ctx)
    assert collided >= 5


def test_triple_emit_row_count_stable(artifacts):
    """Three successive emits must keep dossier cardinality equal to corpora size."""
    _d, _t, closed = artifacts
    expected = len(closed["instances"]) + len(_arm_cases())
    for _ in range(3):
        run_emit_verify()
        dossier = json.loads(DOSSIER.read_text())
        assert len(dossier["dossier_rows"]) == expected


def test_triple_emit_seals_remain_formula_true(artifacts):
    """After three emits, every closed seal must still match the annex material."""
    _d, _t, closed = artifacts
    for _ in range(3):
        run_emit_verify()
    dossier = json.loads(DOSSIER.read_text())
    for inst in closed["instances"]:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])
        assert row["boosted_score"] == expected_boosted(
            inst["left"], inst["right"], inst["nest_depth"], inst["boost"]
        )


def test_edge_arms_survive_multi_emit_merge(artifacts):
    """edge_arms must remain on arm-omit and closed rows after a second emit."""
    _d, _t, closed = artifacts
    run_emit_verify()
    dossier = json.loads(DOSSIER.read_text())
    for inst in closed["instances"][:20]:
        row = _row_by_id(dossier, inst["instance_id"])
        assert row["edge_arms"] == ["core", "west", "east"]
    for ao in _arm_cases()[:10]:
        row = _row_by_id(dossier, ao["case_id"])
        assert ao["omitted_arm"] in row["edge_arms"]
        assert "core" in row["edge_arms"]


def test_recovery_digest_stable_after_poisoned_prior(artifacts):
    """recovery_digest must stay formula-true after prior-epoch journal poison."""
    _d, _t, closed = artifacts
    run_emit_verify()
    for name in ("suite_a.jsonl", "suite_b.jsonl", "suite_c.jsonl", "arm_omit.jsonl"):
        path = JOURNAL / name
        if not path.exists():
            continue
        poisoned = []
        for line in _load_shard(name):
            line = dict(line)
            line["seal_hex"] = "f" * 64
            poisoned.append(json.dumps(line, separators=(",", ":")))
        path.write_text("\n".join(poisoned) + ("\n" if poisoned else ""))
    run_emit_verify()
    transcript = json.loads(TRANSCRIPT.read_text())
    replays = []
    for inst in closed["instances"]:
        rec = _tr_by_id(transcript, inst["instance_id"])
        replays.append(rec["replay_digest"])
    replays.sort()
    assert transcript["recovery_digest"] == sha256_hex(json.dumps(replays, separators=(",", ":")))


def test_wrap_boundary_boosted_scores_present(artifacts):
    """Corpus must exercise boosted_score wrap endpoints 0 and 96 with correct seals."""
    dossier, _t, closed = artifacts
    cmap = _closed_map(closed)
    saw0 = saw96 = False
    for row in dossier["dossier_rows"]:
        iid = row["instance_id"]
        if iid not in cmap:
            continue
        inst = cmap[iid]
        want = expected_boosted(inst["left"], inst["right"], inst["nest_depth"], inst["boost"])
        assert row["boosted_score"] == want
        if want == 0:
            saw0 = True
            assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])
        if want == 96:
            saw96 = True
            assert row["seal_hex"] == expected_seal(row["row_payload"], row["ctx_tag"])
    assert saw0 and saw96


def test_journal_epoch_advances_monotone(artifacts):
    """Each emit must advance journal_epoch by exactly one."""
    _d, _t, _c = artifacts
    e0 = int(STAMP.read_text().strip())
    run_emit_verify()
    e1 = int(STAMP.read_text().strip())
    run_emit_verify()
    e2 = int(STAMP.read_text().strip())
    assert e1 == e0 + 1
    assert e2 == e1 + 1
    assert json.loads(DOSSIER.read_text())["journal_epoch"] == e2


def test_current_epoch_line_count_matches_corpora(artifacts):
    """Current-epoch journal lines across four shards must cover full corpora."""
    _d, _t, closed = artifacts
    run_emit_verify()
    dossier = json.loads(DOSSIER.read_text())
    epoch = dossier["journal_epoch"]
    ids = set()
    for name in ("suite_a.jsonl", "suite_b.jsonl", "suite_c.jsonl", "arm_omit.jsonl"):
        for line in _load_shard(name):
            if line.get("epoch") == epoch:
                ids.add(line["instance_id"])
    want = {i["instance_id"] for i in closed["instances"]} | {a["case_id"] for a in _arm_cases()}
    assert ids == want
