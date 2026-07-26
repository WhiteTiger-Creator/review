"""Domain checks for tabular L0 counterfactual artifacts."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
ENV = Path("/app/environment")
OUT = APP / "output"
ACC_FLOOR = 0.70
FLIP_FLOOR = 0.55
MAX_L0 = 3
MAX_N = 220
DIM = 16


def fnv1a64(data: bytes) -> int:
    h = 0xCBF29CE484222325
    for b in data:
        h ^= b
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def digest_v(v: list[float]) -> str:
    joined = ",".join(f"{float(x):.3f}" for x in v)
    return f"{fnv1a64(joined.encode()):016x}"


def js_stringify_array(vals: list[float]) -> str:
    parts: list[str] = []
    for x in vals:
        fx = float(x)
        if abs(fx - round(fx)) < 1e-9:
            parts.append(str(round(fx)))
        else:
            parts.append(format(fx, ".12g"))
    return "[" + ",".join(parts) + "]"


def load_csv(path: Path) -> list[dict]:
    lines = path.read_text().strip().splitlines()
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split(",")
        rows.append(
            {
                "id": parts[0].strip(),
                "grp": parts[1].strip(),
                "tier": parts[2].strip(),
                "mag": float(parts[3].strip()),
                "tgt": float(parts[4].strip()) if parts[4].strip() else None,
            }
        )
    return rows


def primary_vocab() -> dict[str, list[str]]:
    g: set[str] = set()
    t: set[str] = set()
    for r in load_csv(ENV / "data" / "prime_batch.csv"):
        if r["grp"]:
            g.add(r["grp"])
        if r["tier"]:
            t.add(r["tier"])
    return {"g": sorted(g), "t": sorted(t)}


def encode_expected(row: dict, layout: dict) -> list[float]:
    v = [0.0] * int(layout["dim"])
    r0 = int(layout["r0"])
    r1 = int(layout["r1"])
    offs = layout["offs"]
    vocab = layout["vocab"]

    def slot(tok: str, field: str, off_key: str) -> int:
        if tok == "":
            return r0
        lst = vocab[field]
        if tok not in lst:
            return r1
        return int(offs[off_key]) + lst.index(tok)

    v[slot(row["grp"], "g", "g")] = 1.0
    v[slot(row["tier"], "t", "t")] = 1.0
    v[int(offs["nx"])] = float(row["mag"]) * float(layout["scale"])
    return v


def _apply_mut(row: dict, mut: list) -> dict:
    out = dict(row)
    for m in mut:
        k = m["k"]
        if k in ("grp", "tier", "mag"):
            out[k] = m["b"]
    return out


def _row_payload_ok(row: dict, layout: dict, t: dict) -> bool:
    mut_row = _apply_mut(row, t["mut"]) if t["mut"] else row
    enc = encode_expected(mut_row, layout)
    nbytes = len(js_stringify_array(enc).encode("utf-8"))
    return (
        isinstance(t["mut"], list)
        and len(enc) == int(layout["dim"])
        and digest_v(enc) == t["enc_digest"]
        and int(t["nbytes"]) == nbytes
        and int(t["nbytes"]) <= MAX_N
    )


def run_pipeline() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["npx", "tsx", "/app/environment/run_fit/main.ts"],
        cwd="/app/environment",
        check=True,
    )
    subprocess.run(
        [
            "npx",
            "tsx",
            "/app/environment/run_cf/main.ts",
            "--verify",
            "/app/output/cf_trace.json",
        ],
        cwd="/app/environment",
        check=True,
    )


@pytest.fixture(scope="module")
def artifacts():
    run_pipeline()
    layout = json.loads((OUT / "layout.json").read_text())
    bundle = json.loads((OUT / "bundle.json").read_text())
    scorecard = json.loads((OUT / "scorecard.json").read_text())
    cf = json.loads((OUT / "cf_trace.json").read_text())
    return {
        "layout": layout,
        "bundle": bundle,
        "scorecard": scorecard,
        "cf": cf,
    }


def test_p8_sk_bind(artifacts):
    """Secondary encodings match layout slots and digests after mutation."""
    layout = artifacts["layout"]
    hold = load_csv(ENV / "data" / "blank_rows.csv") + load_csv(
        ENV / "data" / "novel_rows.csv"
    )
    by_id = {r["id"]: r for r in artifacts["cf"]["rows"]}
    checked = sum(1 for row in hold if _row_payload_ok(row, layout, by_id[row["id"]]))
    assert int(layout["dim"]) == DIM and len(by_id) >= 40 and checked >= 40


def test_m2_ql_void(artifacts):
    """Blank cells land on reserved r0 in the layout-backed codec."""
    layout = artifacts["layout"]
    r0 = int(layout["r0"])
    blank_rows = load_csv(ENV / "data" / "blank_rows.csv")
    blank_ok = any(
        encode_expected(row, layout)[r0] == 1.0
        for row in blank_rows
        if row["grp"] == "" or row["tier"] == ""
    )
    blank_ids = {r["id"] for r in blank_rows}
    hits = [
        r
        for r in artifacts["cf"]["rows"]
        if r["id"] in blank_ids and r["y1"] != r["y0"]
    ]
    assert blank_ok and len(hits) >= 1


def test_v5_tr_new(artifacts):
    """Unseen tokens remap through fitted vocab unknown path (r1)."""
    layout = artifacts["layout"]
    r1 = int(layout["r1"])
    vocab_g = set(layout["vocab"]["g"])
    vocab_t = set(layout["vocab"]["t"])
    novel = load_csv(ENV / "data" / "novel_rows.csv")
    assert all(
        row["grp"] not in vocab_g
        and row["tier"] not in vocab_t
        and encode_expected(row, layout)[r1] >= 1.0
        for row in novel
    )


def test_h4_rf_rate(artifacts):
    """Scored class changes meet the public flip-rate and accuracy floors."""
    m = artifacts["scorecard"]
    flipped = [r for r in artifacts["cf"]["rows"] if r["y1"] != r["y0"]]
    assert (
        float(m["acc"]) >= ACC_FLOOR
        and float(m["flip_rate"]) >= FLIP_FLOOR
        and int(m["n_rows"]) >= 40
        and flipped
        and all(1 <= int(r["l0"]) <= MAX_L0 and int(r["nbytes"]) <= MAX_N for r in flipped)
    )


def test_s1_bk_reload(artifacts):
    """Reloaded bundle matches on-disk weights and layout fields."""
    layout = artifacts["layout"]
    bundle = artifacts["bundle"]
    re_layout = json.loads((OUT / "layout.json").read_text())
    re_bundle = json.loads((OUT / "bundle.json").read_text())
    assert (
        int(layout["dim"]) == DIM
        and len(bundle["w"]) == DIM
        and layout["vocab"] == primary_vocab()
        and int(layout["r0"]) != int(layout["r1"])
        and re_layout == layout
        and re_bundle == bundle
        and sum(abs(float(x)) for x in bundle["w"]) > 1.0
    )


def test_j9_ad_edge(artifacts):
    """Unseen secondary still yields schema-valid L0 mutations."""
    layout = artifacts["layout"]
    unseen = load_csv(ENV / "data" / "novel_rows.csv")
    by_id = {r["id"]: r for r in artifacts["cf"]["rows"]}
    ok = 0
    for row in unseen:
        t = by_id[row["id"]]
        if t["y1"] == t["y0"]:
            continue
        if (
            1 <= int(t["l0"]) <= MAX_L0
            and int(t["nbytes"]) <= MAX_N
            and _row_payload_ok(row, layout, t)
        ):
            ok += 1
    assert ok >= 5


def _recompute_flip_stats(rows: list[dict]) -> tuple[float, float, int]:
    flips = [r for r in rows if r["y1"] != r["y0"] and int(r["l0"]) > 0]
    n = len(rows)
    flip_rate = (len(flips) / n) if n else 0.0
    mean_l0 = (sum(int(r["l0"]) for r in flips) / len(flips)) if flips else 0.0
    return flip_rate, mean_l0, n


def test_w3_ms_agree(artifacts):
    """Reported flip-rate and mean L0 agree with recomputed cf_trace values."""
    flip_rate, mean_l0, n = _recompute_flip_stats(artifacts["cf"]["rows"])
    m = artifacts["scorecard"]
    assert (
        float(m["flip_rate"]) == flip_rate
        and float(m["mean_l0"]) == mean_l0
        and int(m["n_rows"]) == n
        and flip_rate >= FLIP_FLOOR
    )


def test_u6_rp_same(artifacts):
    """Deleting outputs and rerunning run_fit/run_cf yields identical traces."""
    first = json.loads((OUT / "cf_trace.json").read_text())
    first_m = json.loads((OUT / "scorecard.json").read_text())
    run_pipeline()
    second = json.loads((OUT / "cf_trace.json").read_text())
    second_m = json.loads((OUT / "scorecard.json").read_text())
    assert first == second and first_m == second_m and second_m == artifacts["scorecard"]
