"""Domain verifier for adversarial octet-budget evaluator artifacts."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

POLICY = "/app/environment/v1/caps_a.json"
OUT = "/app/output/adv_report.json"
TRACE = "/app/output/spend_trace.jsonl"
WALK_SIDE = "/app/output/walk_side.jsonl"


def _wipe_outputs() -> None:
    out_dir = Path("/app/output")
    if out_dir.exists():
        for child in out_dir.iterdir():
            if child.name == "probe":
                if child.is_dir():
                    shutil.rmtree(child)
                child.mkdir(parents=True, exist_ok=True)
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    Path("/app/output/probe").mkdir(parents=True, exist_ok=True)


def _run_driver() -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "bash",
            "/app/environment/cli/hx_drv.sh",
            "--policy",
            "/app/environment/v1/caps_a.json",
            "--cases",
            "/app/environment/k2/demo",
            "--out",
            "/app/output/adv_report.json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def _load_report() -> dict:
    with open(OUT, encoding="utf-8") as fh:
        return json.load(fh)


def _load_policy() -> dict:
    with open(POLICY, encoding="utf-8") as fh:
        return json.load(fh)


def _load_jsonl(path: str) -> list:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _run_by_id(report: dict) -> dict:
    return {row["fixture_id"]: row for row in report["runs"]}


def _sha_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _hex16(text: str) -> str:
    return _sha_hex(text.encode())[:16]


def _canon_digest(obj: dict) -> str:
    # Canonicalization matches form_shape.md (jq -c -S . then sha256, first 16 hex).
    raw = subprocess.check_output(
        ["jq", "-c", "-S", "."],
        input=json.dumps(obj).encode(),
    )
    return _sha_hex(raw)[:16]


def _defense(cols: dict) -> dict:
    out = {k: dict(v) for k, v in cols.items()}
    out["f1"]["v"] = abs(float(out["f1"]["v"]))
    out["f3"]["v"] = max(0.0, min(4.0, float(out["f3"]["v"])))
    return out


def _label_of(rec: dict) -> int:
    cols = _defense(rec["cols"])
    score = (
        2.0 * float(cols["f0"]["v"])
        + (-4.0) * float(cols["f1"]["v"])
        + 1.0 * float(cols["f2"]["v"])
        + 3.0 * float(cols["f3"]["v"])
        + (-2.0)
    )
    return 1 if score >= 0 else 0


def _wiresize(base: dict, cand: dict) -> int:
    total = 0
    for key, cell in base["cols"].items():
        if float(cell["v"]) != float(cand["cols"][key]["v"]):
            total += 2 + int(cell["w"])
    return total


def _mutated_frozen(base: dict, cand: dict) -> int:
    mutable = set(base.get("meta", {}).get("mutable", []))
    for key, cell in base["cols"].items():
        if float(cell["v"]) != float(cand["cols"][key]["v"]) and (
            not cell.get("mut", False) and key not in mutable
        ):
            return 1
    return 0


def _fixture_path(fid: str) -> Path:
    demo = Path("/app/environment/k2/demo") / f"{fid}.json"
    if demo.is_file():
        return demo
    return Path("/app/environment/k2/xtra") / f"{fid}.json"


def _load_fixture(fid: str) -> dict:
    with open(_fixture_path(fid), encoding="utf-8") as fh:
        return json.load(fh)


def _selected_cand(fid: str, report_row: dict) -> dict:
    """Recover selected candidate by matching cand_digest among mutable neighbors."""
    base = _load_fixture(fid)
    keys = [
        k
        for k, cell in base["cols"].items()
        if cell.get("mut") or k in base.get("meta", {}).get("mutable", [])
    ]
    vals = [-10, -2, 0, 2, 3, 4, 5]
    target = report_row["cand_digest"]
    # single-column edits
    for key in keys:
        for val in vals:
            if float(base["cols"][key]["v"]) == float(val):
                continue
            cand = json.loads(json.dumps(base))
            cand["cols"][key]["v"] = float(val)
            if _canon_digest(cand) == target:
                return cand
    # pairwise edits matching oracle search envelope
    pair_vals_a = [2, 3, 4]
    pair_vals_b = [0, 2, 3]
    n = len(keys)
    for a in range(n):
        for b in range(a + 1, n):
            k1, k2 = keys[a], keys[b]
            for v1 in pair_vals_a:
                for v2 in pair_vals_b:
                    cand = json.loads(json.dumps(base))
                    cand["cols"][k1]["v"] = float(v1)
                    cand["cols"][k2]["v"] = float(v2)
                    if _canon_digest(cand) == target:
                        return cand
    return base


def test_alpha_cut_bound():
    """Illegal mutations of frozen columns flip heldout schema envelopes."""
    _wipe_outputs()
    _run_driver()
    policy = _load_policy()
    report = _load_report()
    by_id = _run_by_id(report)
    assert "h3" in by_id
    row = by_id["h3"]
    assert int(row["flip_hit"]) == 1
    assert int(row["octet_spend"]) <= int(policy["octet_budget"])
    cand = _selected_cand("h3", row)
    base = _load_fixture("h3")
    assert _mutated_frozen(base, cand) == 0
    assert _label_of(cand) == int(policy["flip_target"])
    assert _label_of(base) != int(policy["flip_target"])


def test_beta_rerun_stamp():
    """Wipe+rerun regenerates stable mutation-dependent stamps."""
    _wipe_outputs()
    _run_driver()
    first = _run_by_id(_load_report())
    stamps = {fid: (row["cand_digest"], row["side_hex"]) for fid, row in first.items()}
    assert first["h3"]["flip_hit"] == 1
    _wipe_outputs()
    _run_driver()
    second = _run_by_id(_load_report())
    for fid, pair in stamps.items():
        assert fid in second
        assert second[fid]["cand_digest"] == pair[0]
        assert second[fid]["side_hex"] == pair[1]


def test_gamma_wall_bound():
    """Octet spend respects octet_budget on demo case after TLV packing."""
    _wipe_outputs()
    _run_driver()
    policy = _load_policy()
    report = _load_report()
    by_id = _run_by_id(report)
    assert "case_a" in by_id
    row = by_id["case_a"]
    assert int(row["flip_hit"]) == 1
    assert int(row["octet_spend"]) <= int(policy["octet_budget"])
    base = _load_fixture("case_a")
    cand = _selected_cand("case_a", row)
    real = _wiresize(base, cand)
    assert real == int(row["octet_spend"])
    assert real <= int(policy["octet_budget"])


def test_delta_bind_join():
    """adv_report.json counters join spend_trace.jsonl."""
    _wipe_outputs()
    _run_driver()
    report = _load_report()
    rows = _load_jsonl(TRACE)
    assert rows, "spend_trace.jsonl must be non-empty"
    by_id = _run_by_id(report)
    for run in report["runs"]:
        fid = run["fixture_id"]
        picked = [r for r in rows if r.get("fixture_id") == fid and int(r.get("picked", 0)) == 1]
        assert len(picked) == 1, f"expected one picked trace row for {fid}"
        assert int(picked[0]["spend"]) == int(run["octet_spend"])
        assert int(run["flip_hit"]) == 1
        assert fid in by_id


def test_epsilon_parity_lane():
    """Seeded walks keep determinism digests within documented rules."""
    _wipe_outputs()
    _run_driver()
    policy = _load_policy()
    report = _load_report()
    sides = {r["fixture_id"]: r for r in _load_jsonl(WALK_SIDE)}
    seed = str(policy["seed"])
    for run in report["runs"]:
        fid = run["fixture_id"]
        assert fid in sides
        assert sides[fid]["walk_digest"] == run["walk_digest"]
        order = sides[fid]["order_csv"].split(",") if sides[fid]["order_csv"] else []
        # recompute seed order keys for stability check
        keyed = sorted(
            ((_sha_hex(f"{seed}:{name}".encode()), name) for name in order),
            key=lambda x: x[0],
        )
        recomputed = [n for _, n in keyed]
        assert recomputed == order
        assert _hex16(sides[fid]["order_csv"]) == run["walk_digest"]


def test_zeta_sidecar_join():
    """Walk sidecar fields align with report digest inputs."""
    _wipe_outputs()
    _run_driver()
    report = _load_report()
    sides = {r["fixture_id"]: r for r in _load_jsonl(WALK_SIDE)}
    for run in report["runs"]:
        assert isinstance(run["side_hex"], str) and run["side_hex"]
        assert isinstance(run["walk_digest"], str) and run["walk_digest"]
        assert len(run["side_hex"]) == 16
        assert len(run["walk_digest"]) == 16
        assert run["seed"] == report["seed"]
        side = sides[run["fixture_id"]]
        assert side["walk_digest"] == run["walk_digest"]
        expect_side = _hex16(f"{run['fixture_id']}|{run['octet_spend']}|{run['cand_digest']}")
        assert run["side_hex"] == expect_side


def test_eta_mode_match():
    """Heldout defense-sensitive cases keep flip success through veil path."""
    _wipe_outputs()
    _run_driver()
    policy = _load_policy()
    by_id = _run_by_id(_load_report())
    assert "h2" in by_id
    row = by_id["h2"]
    assert int(row["flip_hit"]) == 1
    base = _load_fixture("h2")
    cand = _selected_cand("h2", row)
    assert _label_of(base) != int(policy["flip_target"])
    assert _label_of(cand) == int(policy["flip_target"])
    assert int(row["octet_spend"]) <= int(policy["octet_budget"])
    assert _wiresize(base, cand) == int(row["octet_spend"])


def test_theta_ablate_trap():
    """Defense-path heldout fails envelopes when veil path is wrong."""
    _wipe_outputs()
    _run_driver()
    policy = _load_policy()
    by_id = _run_by_id(_load_report())
    row = by_id["h2"]
    base = _load_fixture("h2")
    cand = _selected_cand("h2", row)
    assert _label_of(cand) == int(policy["flip_target"])
    assert int(row["adv_label"]) == _label_of(cand)
    assert int(row["base_label"]) == _label_of(base)
    assert _load_report()["seed"] == policy["seed"]
    assert len(_load_jsonl(TRACE)) > 0
