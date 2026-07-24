"""Differential replay dossier domain checks."""

import json
import subprocess
from pathlib import Path

APP = Path("/app")
OUT = APP / "output" / "diff_replay_dossier.json"
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


def visit_order(pack: dict, apply_permute: bool) -> list[str]:
    permute = pack.get("permute_order") or []
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


def narrowed_labels(pack: dict, apply_permute: bool) -> dict[str, str]:
    order = visit_order(pack, apply_permute)
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


def expected_margins(pack: dict, apply_permute: bool, wave: str | None = None) -> list[int]:
    table = load_table()
    keys = table["row_keys"]
    bases = pack_bases(pack)
    hashes = table["cue_hashes"]
    labels = narrowed_labels(pack, apply_permute)
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


def trace_cluster_sequence(pack: dict, apply_permute: bool) -> list[str]:
    table = load_table()
    order = visit_order(pack, apply_permute) if (apply_permute and pack.get("permute_order")) else list(table["row_keys"])
    if not order:
        return []
    return order + [order[-1]]


def expected_replay_deltas(arm_id: int, margins: list[int], trace_seq: list[str]) -> list[dict]:
    row_keys = load_table()["row_keys"]
    prev: dict[str, int] = {}
    deltas = []
    for step, cid in enumerate(trace_seq):
        idx = row_keys.index(cid)
        margin = margins[idx]
        if cid in prev:
            delta = margin - prev[cid]
        else:
            delta = 0
        prev[cid] = margin
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


def ref_table_bases_margins(pack: dict, apply_permute: bool) -> list[int]:
    table = load_table()
    labels = narrowed_labels(pack, apply_permute)
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


def test_m7_qz_emit() -> None:
    """Direct mode: witness rows and barrier margins must match values recomputed from fixture packs."""
    report = run_diff("direct")
    pack = load_pack("pack_t352.json")
    table = load_table()
    expected = expected_margins(pack, apply_permute=False)
    trace_seq = trace_cluster_sequence(pack, apply_permute=False)
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
    assert direct["barrier_margins"] == expected_margins(direct_pack, apply_permute=False)
    assert held["barrier_margins"] == expected_margins(held_pack, apply_permute=True)


def test_idempo_dup() -> None:
    """Two identical direct runs must yield the same witness refs and merge token with no duplicates."""
    first = run_diff("direct")
    second = run_diff("direct")
    refs_first = [row["ref"] for row in first["witness_rows"]]
    refs_second = [row["ref"] for row in second["witness_rows"]]
    assert refs_first == refs_second
    assert first["merge_token"] == second["merge_token"]
    assert len(refs_second) == len(set(refs_second))


def test_v3_trace_permute_order() -> None:
    """Held+permute: replay deltas must follow permute order, fork the last cluster, and match recomputed margins."""
    report = run_diff("held", permute=True)
    pack = load_pack("pack_h0352.json")
    order = visit_order(pack, apply_permute=True)
    expected = expected_margins(pack, apply_permute=True)
    trace_seq = trace_cluster_sequence(pack, apply_permute=True)
    cluster_seq = [row["cluster_id"] for row in report["replay_deltas"][:3]]
    assert cluster_seq == order
    assert report["replay_deltas"][3]["cluster_id"] == order[-1]
    assert report["replay_deltas"] == expected_replay_deltas(pack["arm_id"], expected, trace_seq)
    assert report["barrier_margins"] == expected


def test_z2_held_margin_bases() -> None:
    """Held+permute margins must use pack margin_bases rather than reference table_bases alone."""
    report = run_diff("held", permute=True)
    pack = load_pack("pack_h0352.json")
    table = load_table()
    expected = expected_margins(pack, apply_permute=True)
    assert pack["margin_bases"] != table["table_bases"]
    assert report["barrier_margins"] == expected
    assert report["barrier_margins"] != ref_table_bases_margins(pack, apply_permute=True)


def test_fork_x9() -> None:
    """Direct mode: fork replay deltas for a cluster must be consistent; witness margins must match barrier vector."""
    report = run_diff("direct")
    table = load_table()
    by_cluster: dict[str, list[int]] = {}
    for row in report["replay_deltas"]:
        cluster_id = row["cluster_id"]
        if cluster_id not in by_cluster:
            by_cluster[cluster_id] = []
        by_cluster[cluster_id].append(row["delta"])
    for deltas in by_cluster.values():
        if len(deltas) > 1:
            assert len(set(deltas)) == 1
    margins = {row["cluster_id"]: row["margin"] for row in report["witness_rows"]}
    for row in report["witness_rows"]:
        idx = table["row_keys"].index(row["cluster_id"])
        assert row["margin"] == report["barrier_margins"][idx]
        assert row["margin"] == margins[row["cluster_id"]]


def test_h2_wk_term() -> None:
    """Stress w0: active-arm draw weight must meet termination threshold; margins match recomputed w0 values."""
    report = run_diff("stress", wave="w0")
    pack = load_pack("pack_t352.json")
    expected = expected_margins(pack, apply_permute=False, wave="w0")
    assert stress_w0_active_arm_weight_sum(pack) >= termination_threshold()
    assert report["barrier_margins"] == expected


def test_w9_arm_draw() -> None:
    """Stress w0: full barrier margin vector must match recomputed values with foreign-arm draws excluded."""
    report = run_diff("stress", wave="w0")
    pack = load_pack("pack_t352.json")
    expected = expected_margins(pack, apply_permute=False, wave="w0")
    table = load_table()
    c1 = table["row_keys"].index("c1")
    assert report["barrier_margins"][c1] == expected[c1]
    assert report["barrier_margins"] == expected


def test_q8_merge_token_bind() -> None:
    """Direct mode: merge_token must match the digest recomputed from sorted witness refs, case id, and run mode."""
    report = run_diff("direct")
    refs = sorted(row["ref"] for row in report["witness_rows"])
    expected = merge_token(report["case_id"], report["run_mode"], refs)
    assert report["merge_token"] == expected
    pack = load_pack("pack_t352.json")
    margins = expected_margins(pack, apply_permute=False)
    trace_seq = trace_cluster_sequence(pack, apply_permute=False)
    assert len(refs) == len(expected_witness_rows(pack["arm_id"], margins, trace_seq))


def test_p4_nq_rotate() -> None:
    """Stress w0 and w1 must produce different margins, each matching its recomputed wave-specific vector."""
    w0 = run_diff("stress", wave="w0")
    w1 = run_diff("stress", wave="w1")
    pack = load_pack("pack_t352.json")
    expected_w0 = expected_margins(pack, apply_permute=False, wave="w0")
    expected_w1 = expected_margins(pack, apply_permute=False, wave="w1")
    assert w0["barrier_margins"] != w1["barrier_margins"]
    assert w0["barrier_margins"] == expected_w0
    assert w1["barrier_margins"] == expected_w1
