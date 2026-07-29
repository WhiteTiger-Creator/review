"""Differential replay dossier domain checks."""

import json
import subprocess
from pathlib import Path

APP = Path("/app")
OUT = APP / "output" / "diff_replay_dossier.json"
JOURNAL = APP / "output" / "replay_journal.json"
DATA = APP / "environment" / "app" / "data"


def load_pack(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def load_table() -> dict:
    return json.loads((DATA / "ref_q7_pack.json").read_text(encoding="utf-8"))


def load_draws_doc() -> dict:
    return json.loads((DATA / "k9_k7_pack.json").read_text(encoding="utf-8"))


def label_rank(label: str) -> int:
    return int(label[1])


def arm_salt(arm_id: int) -> int:
    return (arm_id * 131) % 997


def pack_bases(pack: dict) -> list[int]:
    table = load_table()
    if pack.get("margin_bases"):
        return pack["margin_bases"]
    return table["table_bases"]


def wave_scale(wave: str) -> int:
    doc = load_draws_doc()
    return doc.get("wave_scale", {}).get(wave, 3)


def visit_order(pack: dict, apply_permute: bool, held_mode: bool = False) -> list[str]:
    permute = pack.get("permute_order") or []
    if held_mode and permute:
        return list(permute)
    if permute and apply_permute:
        return list(permute)
    return [cluster["cluster_id"] for cluster in pack["cue_clusters"]]


def cue_slice(cluster: dict) -> bytes:
    raw = bytes(int(cluster["cue_bytes"][i : i + 2], 16) for i in range(0, len(cluster["cue_bytes"]), 2))
    padded = bytearray(raw)
    while len(padded) < 8:
        padded.append(0)
    if cluster.get("boundary"):
        padded[4] |= 0x01
    return bytes(padded)


def narrowed_labels(pack: dict, apply_permute: bool = False, held_mode: bool = False) -> dict[str, str]:
    order = visit_order(pack, apply_permute, held_mode)
    clusters = {cluster["cluster_id"]: cluster for cluster in pack["cue_clusters"]}
    labels = {cid: pack["label_map"][cid] for cid in order}
    out: dict[str, str] = {}
    for cid in order:
        label = labels[cid]
        cluster = clusters[cid]
        slice_bytes = cue_slice(cluster)
        if (slice_bytes[4] & 0x01) != 0:
            neighbor = labels[cluster["neighbor_id"]]
            rank = min(label_rank(label), label_rank(neighbor))
            label = f"L{rank}"
        labels[cid] = label
        out[cid] = label
    return out


def expected_margins(
    pack: dict,
    apply_permute: bool = False,
    wave: str | None = None,
    held_mode: bool = False,
) -> list[int]:
    table = load_table()
    keys = table["row_keys"]
    bases = pack_bases(pack)
    hashes = table["cue_hashes"]
    labels = narrowed_labels(pack, apply_permute, held_mode)
    salt = arm_salt(pack["arm_id"])
    boost: dict[str, int] = {}
    if wave is not None:
        scale = wave_scale(wave)
        for draw in load_draws_doc()["draws"]:
            if draw["wave"] == wave and draw["arm_id"] == pack["arm_id"]:
                cid = draw["cluster_id"]
                boost[cid] = boost.get(cid, 0) + int(draw["weight"] * scale)
    margins = []
    for i, cid in enumerate(keys):
        rank = label_rank(labels[cid])
        margins.append(hashes[i] + salt + rank - bases[i] + boost.get(cid, 0))
    return margins


def sha256_hex(data: str) -> str:
    proc = subprocess.run(
        ["sha256sum"],
        input=data.encode(),
        capture_output=True,
        check=True,
    )
    return proc.stdout.decode().split()[0]


def witness_ref(arm_id: int, cluster_id: str, margin: int) -> str:
    raw = f"{arm_id}|{cluster_id}|{margin}"
    return "w-" + sha256_hex(raw)[:12]


def merge_token(case_id: int, run_mode: str, refs: list[str]) -> str:
    body = "|".join(sorted(refs)) + f"|{case_id}|{run_mode}"
    return sha256_hex(body)[:16]


def trace_cluster_sequence(
    pack: dict,
    apply_permute: bool = False,
    mode: str = "direct",
) -> list[str]:
    table = load_table()
    if mode == "held" and not apply_permute:
        order = list(table["row_keys"])
    elif apply_permute and pack.get("permute_order"):
        order = list(pack["permute_order"])
    else:
        order = list(table["row_keys"])
    if not order:
        return []
    return order + [order[-1]]


def stress_carryover(pack: dict, wave: str) -> int:
    weight_sum = sum(
        draw["weight"]
        for draw in load_draws_doc()["draws"]
        if draw["wave"] == wave and draw["arm_id"] == pack["arm_id"]
    )
    excess = weight_sum - termination_threshold()
    if excess <= 0:
        return 0
    return int(excess * 1000)


def expected_replay_deltas(
    arm_id: int,
    margins: list[int],
    trace_seq: list[str],
    fork_carryover: int = 0,
) -> list[dict]:
    row_keys = load_table()["row_keys"]
    prev: dict[str, int] = {}
    deltas = []
    for step, cid in enumerate(trace_seq):
        idx = row_keys.index(cid)
        barrier = margins[idx]
        is_fork = step == len(trace_seq) - 1 and step > 0 and cid == trace_seq[-1]
        step_margin = barrier + (fork_carryover if is_fork and fork_carryover > 0 else 0)
        if cid in prev:
            delta = step_margin - prev[cid]
        else:
            delta = 0
        prev[cid] = step_margin
        deltas.append({"step": step, "arm_id": arm_id, "cluster_id": cid, "delta": delta})
    return deltas


def expected_witness_rows(arm_id: int, margins: list[int], trace_seq: list[str]) -> list[dict]:
    row_keys = load_table()["row_keys"]
    rows: list[dict] = []
    seen: set[str] = set()
    for cid in trace_seq:
        if cid in seen:
            continue
        seen.add(cid)
        idx = row_keys.index(cid)
        margin = margins[idx]
        rows.append(
            {
                "arm_id": arm_id,
                "cluster_id": cid,
                "margin": margin,
                "ref": witness_ref(arm_id, cid, margin),
            }
        )
    return rows


def ref_table_bases_margins(pack: dict, apply_permute: bool, held_mode: bool = False) -> list[int]:
    table = load_table()
    labels = narrowed_labels(pack, apply_permute, held_mode)
    salt = arm_salt(pack["arm_id"])
    margins = []
    for i, cid in enumerate(table["row_keys"]):
        rank = label_rank(labels[cid])
        margins.append(table["cue_hashes"][i] + salt + rank - table["table_bases"][i])
    return margins


def stress_w0_active_arm_weight_sum(pack: dict) -> float:
    return sum(
        draw["weight"]
        for draw in load_draws_doc()["draws"]
        if draw["wave"] == "w0" and draw["arm_id"] == pack["arm_id"]
    )


def termination_threshold() -> float:
    return float(load_draws_doc()["termination_weight"])


def run_diff(
    mode: str,
    wave: str | None = None,
    permute: bool = False,
    journal: Path | None = None,
    resume: Path | None = None,
    expect_fail: bool = False,
) -> dict | None:
    if OUT.exists():
        OUT.unlink()
    subprocess.run(["make", "-C", "/app/environment"], check=True)
    invocation = ["/app/exec/diff_run", "--case", "352", "--mode", mode]
    if mode == "held" and permute:
        invocation.append("--permute")
    if mode == "stress" and wave:
        invocation.extend(["--wave", wave])
    if journal is not None:
        invocation.extend(["--journal", str(journal)])
    if resume is not None:
        invocation.extend(["--resume", str(resume)])
    proc = subprocess.run(invocation, capture_output=True, text=True, check=False)
    if expect_fail:
        assert proc.returncode != 0, proc.stderr or proc.stdout
        return None
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert OUT.is_file()
    return json.loads(OUT.read_text(encoding="utf-8"))


def test_m7_direct_emit() -> None:
    """Direct mode: witness rows, barrier margins, and replay_epoch must match recomputed contract values."""
    report = run_diff("direct")
    pack = load_pack("pack_t352.json")
    table = load_table()
    expected = expected_margins(pack)
    trace_seq = trace_cluster_sequence(pack, mode="direct")
    assert report["replay_epoch"] == 0
    assert report["barrier_margins"] == expected
    assert report["witness_rows"] == expected_witness_rows(pack["arm_id"], expected, trace_seq)
    for row in report["witness_rows"]:
        idx = table["row_keys"].index(row["cluster_id"])
        assert row["margin"] == report["barrier_margins"][idx]


def test_n4_pl_pair() -> None:
    """Held permute margins must differ from direct mode and match recomputed held-pack values."""
    direct = run_diff("direct")
    held = run_diff("held", permute=True)
    direct_pack = load_pack("pack_t352.json")
    held_pack = load_pack("pack_h0352.json")
    assert direct["barrier_margins"] != held["barrier_margins"]
    assert direct["barrier_margins"] == expected_margins(direct_pack)
    assert held["barrier_margins"] == expected_margins(held_pack, apply_permute=True, held_mode=True)


def test_j4_journal_resume_epoch() -> None:
    """Journal resume must increment replay_epoch while preserving merge token and witness refs."""
    if JOURNAL.exists():
        JOURNAL.unlink()
    first = run_diff("direct", journal=JOURNAL)
    assert first["replay_epoch"] == 0
    assert JOURNAL.is_file()
    second = run_diff("direct", journal=JOURNAL, resume=JOURNAL)
    assert second["replay_epoch"] == 1
    refs_first = [row["ref"] for row in first["witness_rows"]]
    refs_second = [row["ref"] for row in second["witness_rows"]]
    assert refs_first == refs_second
    assert first["merge_token"] == second["merge_token"]


def test_v3_trace_permute_order() -> None:
    """Held+permute: replay deltas must follow permute order, fork the last cluster, and match recomputed margins."""
    report = run_diff("held", permute=True)
    pack = load_pack("pack_h0352.json")
    order = visit_order(pack, apply_permute=True, held_mode=True)
    expected = expected_margins(pack, apply_permute=True, held_mode=True)
    trace_seq = trace_cluster_sequence(pack, apply_permute=True, mode="held")
    cluster_seq = [row["cluster_id"] for row in report["replay_deltas"][:3]]
    assert cluster_seq == order
    assert report["replay_deltas"][3]["cluster_id"] == order[-1]
    assert report["replay_deltas"] == expected_replay_deltas(pack["arm_id"], expected, trace_seq)
    assert report["barrier_margins"] == expected


def test_l5_held_narrow_trace_split() -> None:
    """Held without permute: lattice narrowing uses permute_order while trace framing stays on row_keys."""
    held_no_perm = run_diff("held", permute=False)
    held_perm = run_diff("held", permute=True)
    pack = load_pack("pack_h0352.json")
    table = load_table()
    expected = expected_margins(pack, held_mode=True)
    trace_seq = trace_cluster_sequence(pack, mode="held", apply_permute=False)
    assert held_no_perm["barrier_margins"] == expected
    assert held_perm["barrier_margins"] == expected
    cluster_seq = [row["cluster_id"] for row in held_no_perm["replay_deltas"][:3]]
    perm_seq = [row["cluster_id"] for row in held_perm["replay_deltas"][:3]]
    assert cluster_seq == table["row_keys"]
    assert perm_seq == pack["permute_order"]
    assert cluster_seq != perm_seq
    assert held_no_perm["replay_deltas"] == expected_replay_deltas(pack["arm_id"], expected, trace_seq)
    assert held_no_perm["replay_deltas"] != held_perm["replay_deltas"]


def test_z2_held_margin_bases() -> None:
    """Held+permute margins must use pack margin_bases rather than reference table_bases alone."""
    report = run_diff("held", permute=True)
    pack = load_pack("pack_h0352.json")
    table = load_table()
    expected = expected_margins(pack, apply_permute=True, held_mode=True)
    assert pack["margin_bases"] != table["table_bases"]
    assert report["barrier_margins"] == expected
    assert report["barrier_margins"] != ref_table_bases_margins(pack, apply_permute=True, held_mode=True)


def test_f3_stress_fork_carryover() -> None:
    """Stress w0: fork replay delta must equal documented carryover above termination threshold."""
    report = run_diff("stress", wave="w0")
    pack = load_pack("pack_t352.json")
    expected = expected_margins(pack, wave="w0")
    carryover = stress_carryover(pack, "w0")
    assert carryover > 0
    trace_seq = trace_cluster_sequence(pack, mode="stress")
    assert report["replay_deltas"] == expected_replay_deltas(pack["arm_id"], expected, trace_seq, carryover)
    fork_delta = report["replay_deltas"][-1]["delta"]
    assert fork_delta == carryover


def test_h2_wk_term() -> None:
    """Stress w0: active-arm draw weight must meet termination threshold; margins match recomputed w0 values."""
    report = run_diff("stress", wave="w0")
    pack = load_pack("pack_t352.json")
    expected = expected_margins(pack, wave="w0")
    assert stress_w0_active_arm_weight_sum(pack) >= termination_threshold()
    assert report["barrier_margins"] == expected


def test_k1_journal_wave_invalidate() -> None:
    """Resuming a stress w0 journal under w1 must reject with non-zero exit (wave fingerprint mismatch)."""
    if JOURNAL.exists():
        JOURNAL.unlink()
    run_diff("stress", wave="w0", journal=JOURNAL)
    run_diff("stress", wave="w1", resume=JOURNAL, expect_fail=True)


def test_q8_merge_token_bind() -> None:
    """Direct mode: merge_token must match digest recomputed from sorted witness refs, case id, and run mode."""
    report = run_diff("direct")
    refs = sorted(row["ref"] for row in report["witness_rows"])
    expected = merge_token(report["case_id"], report["run_mode"], refs)
    assert report["merge_token"] == expected
    pack = load_pack("pack_t352.json")
    margins = expected_margins(pack)
    trace_seq = trace_cluster_sequence(pack, mode="direct")
    assert len(refs) == len(expected_witness_rows(pack["arm_id"], margins, trace_seq))


def test_p4_nq_rotate() -> None:
    """Stress w0 and w1 must produce different margins, each matching its recomputed wave-specific vector."""
    w0 = run_diff("stress", wave="w0")
    w1 = run_diff("stress", wave="w1")
    pack = load_pack("pack_t352.json")
    expected_w0 = expected_margins(pack, wave="w0")
    expected_w1 = expected_margins(pack, wave="w1")
    assert w0["barrier_margins"] != w1["barrier_margins"]
    assert w0["barrier_margins"] == expected_w0
    assert w1["barrier_margins"] == expected_w1
