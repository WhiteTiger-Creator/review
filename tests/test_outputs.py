"""Differential replay dossier domain checks."""

import json
import subprocess
from pathlib import Path

APP = Path("/app")
OUT = APP / "output" / "diff_replay_dossier.json"
VECTORS = Path(__file__).resolve().parent / "vectors"


def load_vector(name: str):
    return json.loads((VECTORS / name).read_text(encoding="utf-8"))


def run_diff(mode: str, wave: str | None = None, permute: bool = False) -> dict:
    if OUT.exists():
        OUT.unlink()
    subprocess.run(["make", "-C", "/app/environment"], check=True)
    if mode == "direct":
        proc = subprocess.run(
            ["/app/exec/diff_run", "--case", "352", "--mode", "direct"],
            capture_output=True,
            text=True,
            check=False,
        )
    elif mode == "held" and permute:
        proc = subprocess.run(
            ["/app/exec/diff_run", "--case", "352", "--mode", "held", "--permute"],
            capture_output=True,
            text=True,
            check=False,
        )
    elif mode == "stress" and wave == "w0":
        proc = subprocess.run(
            ["/app/exec/diff_run", "--case", "352", "--mode", "stress", "--wave", "w0"],
            capture_output=True,
            text=True,
            check=False,
        )
    elif mode == "stress" and wave == "w1":
        proc = subprocess.run(
            ["/app/exec/diff_run", "--case", "352", "--mode", "stress", "--wave", "w1"],
            capture_output=True,
            text=True,
            check=False,
        )
    else:
        raise AssertionError(f"unsupported diff_run invocation: mode={mode} wave={wave} permute={permute}")
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert OUT.is_file()
    return json.loads(OUT.read_text(encoding="utf-8"))


def assert_witness_rows_match(report: dict, expected_rows: list[dict]) -> None:
    assert report["witness_rows"] == expected_rows


def assert_barrier_margins_match(report: dict, expected_margins: list[int]) -> None:
    assert report["barrier_margins"] == expected_margins


def test_m7_qz_emit() -> None:
    """Direct mode: witness rows and barrier margins must match the frozen direct vector."""
    report = run_diff("direct")
    golden = load_vector("direct.json")
    row_keys = load_vector("rkeys.json")
    assert_barrier_margins_match(report, golden["barrier_margins"])
    assert_witness_rows_match(report, golden["witness_rows"])
    for row in report["witness_rows"]:
        idx = row_keys.index(row["cluster_id"])
        assert row["margin"] == report["barrier_margins"][idx]


def test_n4_pl_pair() -> None:
    """Held permute margins must differ from direct mode and match the frozen held vector."""
    direct = run_diff("direct")
    held = run_diff("held", permute=True)
    direct_golden = load_vector("direct.json")
    held_golden = load_vector("hperm.json")
    assert direct["barrier_margins"] != held["barrier_margins"]
    assert direct["barrier_margins"] == direct_golden["barrier_margins"]
    assert held["barrier_margins"] == held_golden["barrier_margins"]


def test_idempo_dup() -> None:
    """Two identical direct runs must yield the same witness refs and merge token with no duplicates."""
    first = run_diff("direct")
    second = run_diff("direct")
    refs_first = [r["ref"] for r in first["witness_rows"]]
    refs_second = [r["ref"] for r in second["witness_rows"]]
    assert refs_first == refs_second
    assert first["merge_token"] == second["merge_token"]
    assert len(refs_second) == len(set(refs_second))


def test_v3_trace_permute_order() -> None:
    """Held+permute: replay deltas must follow permute order, fork the last cluster, and match frozen margins."""
    report = run_diff("held", permute=True)
    golden = load_vector("hperm.json")
    order = load_vector("pord.json")
    cluster_seq = [row["cluster_id"] for row in report["replay_deltas"][:3]]
    assert cluster_seq == order
    assert report["replay_deltas"][3]["cluster_id"] == order[-1]
    assert report["replay_deltas"] == golden["replay_deltas"]
    assert_barrier_margins_match(report, golden["barrier_margins"])


def test_z2_held_margin_bases() -> None:
    """Held+permute margins must match the frozen held vector and differ from the ref-table negative control."""
    report = run_diff("held", permute=True)
    golden = load_vector("hperm.json")
    neg_control = load_vector("ncrb.json")
    assert_barrier_margins_match(report, golden["barrier_margins"])
    assert report["barrier_margins"] != neg_control


def test_fork_x9() -> None:
    """Direct mode: fork replay deltas for a cluster must be consistent; witness margins must match barrier vector."""
    report = run_diff("direct")
    row_keys = load_vector("rkeys.json")
    by_cluster: dict[str, list[int]] = {}
    for row in report["replay_deltas"]:
        cluster_id = row["cluster_id"]
        if cluster_id not in by_cluster:
            by_cluster[cluster_id] = []
        by_cluster[cluster_id].append(row["delta"])
    for deltas in by_cluster.values():
        if len(deltas) > 1:
            assert len(set(deltas)) == 1
    margins = {r["cluster_id"]: r["margin"] for r in report["witness_rows"]}
    for row in report["witness_rows"]:
        idx = row_keys.index(row["cluster_id"])
        assert row["margin"] == report["barrier_margins"][idx]
        assert row["margin"] == margins[row["cluster_id"]]


def test_h2_wk_term() -> None:
    """Stress w0: active-arm draw weight floor must meet termination threshold; margins match frozen w0 vector."""
    report = run_diff("stress", wave="w0")
    golden = load_vector("sw0.json")
    weight_floor = load_vector("w0wf.json")
    termination_threshold = load_vector("tterm.json")
    assert weight_floor >= termination_threshold
    assert_barrier_margins_match(report, golden["barrier_margins"])


def test_w9_arm_draw() -> None:
    """Stress w0: full barrier margin vector must match frozen w0 vector (foreign-arm draws excluded)."""
    report = run_diff("stress", wave="w0")
    golden = load_vector("sw0.json")
    row_keys = load_vector("rkeys.json")
    c1 = row_keys.index("c1")
    assert report["barrier_margins"][c1] == golden["barrier_margins"][c1]
    assert_barrier_margins_match(report, golden["barrier_margins"])


def test_q8_merge_token_bind() -> None:
    """Direct mode: merge_token must match the frozen direct vector for the witness ref set."""
    report = run_diff("direct")
    golden = load_vector("direct.json")
    assert report["merge_token"] == golden["merge_token"]
    refs = sorted(r["ref"] for r in report["witness_rows"])
    assert len(refs) == len(golden["witness_rows"])


def test_p4_nq_rotate() -> None:
    """Stress w0 and w1 must produce different margins, each matching its frozen wave vector."""
    w0 = run_diff("stress", wave="w0")
    w1 = run_diff("stress", wave="w1")
    w0_golden = load_vector("sw0.json")
    w1_golden = load_vector("sw1.json")
    assert w0["barrier_margins"] != w1["barrier_margins"]
    assert_barrier_margins_match(w0, w0_golden["barrier_margins"])
    assert_barrier_margins_match(w1, w1_golden["barrier_margins"])
