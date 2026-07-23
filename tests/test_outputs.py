"""Domain verifier for compost thermal PMC invariant bundle."""

from __future__ import annotations

import hashlib
import struct
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, "/app/environment/tools")
import digest_pack  # noqa: E402

ENV = Path("/app/environment")
OUT = Path("/app/output/invariant_bundle.yaml")
STAGE = Path("/app/output/stage")
CORPUS = ENV / "data" / "pack_c"
PERM = ENV / "data" / "perm_tbl.toml"
TOL = 1.0e-9


def _rebuild_and_emit() -> None:
    if OUT.exists():
        OUT.unlink()
    if STAGE.exists():
        for path in STAGE.iterdir():
            if path.is_file():
                path.unlink()
    subprocess.run(
        ["/app/environment/tools/build.sh"],
        check=True,
        cwd="/app/environment",
    )
    STAGE.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "/app/environment/tools/hv7",
            "--corpus",
            "/app/environment/data/pack_c",
            "--out",
            "/app/output/invariant_bundle.yaml",
        ],
        check=True,
        cwd="/app/environment",
    )


def _load_bundle() -> dict:
    assert OUT.is_file(), "missing invariant_bundle.yaml"
    return yaml.safe_load(OUT.read_text())


def _parse_simple_toml_tables(path: Path) -> dict:
    text = path.read_text()
    section = ""
    data: dict = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and not line.startswith("[["):
            section = line.strip("[]")
            data.setdefault(section, {})
            continue
        if "=" not in line or line.startswith("[["):
            continue
        k, v = [x.strip() for x in line.split("=", 1)]
        if v.startswith("["):
            continue
        try:
            if "." in v or "e" in v.lower():
                data.setdefault(section, {})[k] = float(v)
            else:
                data.setdefault(section, {})[k] = int(v) if v.isdigit() else float(v)
        except ValueError:
            data.setdefault(section, {})[k] = v.strip('"')
    return data


def _load_nrg() -> dict:
    return _parse_simple_toml_tables(CORPUS / "nrg.toml")


def _load_perms() -> list[tuple[str, list[int]]]:
    text = PERM.read_text()
    out: list[tuple[str, list[int]]] = []
    cur_id = None
    cur_order: list[int] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("[[perm]]"):
            if cur_id is not None:
                out.append((cur_id, cur_order))
            cur_id = None
            cur_order = []
            continue
        if line.startswith("id"):
            cur_id = line.split("=", 1)[1].strip().strip('"')
        if line.startswith("order"):
            rhs = line.split("=", 1)[1].strip().strip("[]")
            cur_order = [int(x.strip()) for x in rhs.split(",") if x.strip()]
    if cur_id is not None:
        out.append((cur_id, cur_order))
    return out


def _load_hints() -> list[int]:
    raw = (CORPUS / "sched.bin").read_bytes()
    return list(struct.unpack("<" + "I" * (len(raw) // 4), raw))


def _layer_count() -> int:
    return sum(1 for ln in (CORPUS / "layers.toml").read_text().splitlines() if "[[slot]]" in ln)


def _arm_list(nrg: dict) -> list[tuple[str, float, list[int]]]:
    train = float(nrg.get("arms.train_a", {}).get("scale", 1.0))
    host = float(nrg.get("arms.host_b", {}).get("scale", 1.05))
    arms = [
        ("train_a", train, [0, 1, 2]),
        ("host_b", host, [0, 1, 2]),
    ]
    for pid, order in _load_perms():
        arms.append((pid, host, order))
    return arms


def _permute_hints(base: list[int], n_layers: int, order: list[int]) -> list[int]:
    out = []
    for i in range(n_layers):
        src = base[i % len(base)]
        rot = order[i % len(order)]
        out.append((src + rot * 3 + i) & 0xFFFFFFFF)
    return out


def _rank(hints: list[int], layer_ix: list[int], hint_mul: int, lane_mul: int) -> list[int]:
    n = min(len(hints), len(layer_ix))
    scores = [((hints[i] * hint_mul) + (layer_ix[i] * lane_mul)) & 0xFFFFFFFF for i in range(n)]
    order = list(range(n))
    order.sort(key=lambda i: (-scores[i], i))
    ranks = [0] * n
    for pos, idx in enumerate(order):
        ranks[idx] = pos
    return ranks


def _thermal_rows(n_layers: int) -> list[list[int]]:
    rows = []
    for i in range(n_layers):
        a = i + 1
        b = ((i + 1) % n_layers) + 1
        rows.append([a, -b])
        rows.append([-a, b])
    return rows


def _matrix_tags(rows: list[list[int]], ranks: list[int]) -> list[int]:
    keyed = []
    for r in rows:
        sk = tuple(sorted(r))
        key = ",".join(str(x) for x in sk)
        keyed.append((key, list(r)))
    keyed.sort(key=lambda x: x[0])
    tags = []
    for i, (_, lits) in enumerate(keyed):
        lits = sorted(lits, key=lambda lit: (ranks[abs(lit) - 1], lit))
        acc = (0xC0FF0000 ^ i) & 0xFFFFFFFF
        for lit in lits:
            rk = ranks[abs(lit) - 1]
            acc = (acc * 16777619 + rk * 37 + (lit & 0xFFFFFFFF)) & 0xFFFFFFFF
        tags.append(acc)
    return sorted(set(tags))


def _assigns(edge_keys: list[str], caps: dict[str, float], scale: float, order: list[int]):
    out = []
    for i, k in enumerate(edge_keys):
        ord_v = order[i % len(order)]
        frac = 0.55 + 0.12 * ord_v
        use = caps[k] * scale * frac
        out.append((k, use * 0.6))
        out.append((k, use * 0.4))
    return out


def _fold(assigns, caps, reclaim, eps):
    uses = {k: 0.0 for k in caps}
    for k, u in assigns:
        uses[k] += u
    viol = 0
    res = {}
    for k in sorted(caps):
        eff = caps[k] - reclaim.get(k, 0.0)
        res[k] = uses[k] - eff
        if uses[k] > eff + eps:
            viol += 1
    util = 0.0
    for k in caps:
        eff = max(caps[k] - reclaim.get(k, 0.0), 1e-12)
        util = max(util, uses[k] / eff)
    return viol, res, util, uses


def _u32(v: int) -> bytes:
    return digest_pack.u32(v)


def _f64(v: float) -> bytes:
    return digest_pack.f64(v)


def reference_bundle() -> dict:
    nrg = _load_nrg()
    tol = float(nrg.get("eps", {}).get("tol", TOL))
    hint_mul = int(nrg.get("mul", {}).get("hint_mul", 65521))
    lane_mul = int(nrg.get("mul", {}).get("lane_mul", 127))
    caps = {k: float(v) for k, v in nrg.get("edges", {}).items()}
    reclaim = {k: float(v) for k, v in nrg.get("reclaim", {}).items()}
    edge_keys = sorted(caps)
    n_layers = _layer_count()
    hints = _load_hints()
    rows = _thermal_rows(n_layers)

    journal = b""
    gen = 0
    out_rows = []
    util_max = 0.0

    for arm_id, scale, order in _arm_list(nrg):
        h = _permute_hints(hints, n_layers, order)
        layer_ix = list(range(n_layers))
        ranks = _rank(h, layer_ix, hint_mul, lane_mul)
        tags = _matrix_tags(rows, ranks)
        assigns = _assigns(edge_keys, caps, scale, order)
        viol, res, util, _uses = _fold(assigns, caps, reclaim, tol)
        util_max = max(util_max, util)

        gen = (gen + 1) & 0xFFFFFFFF
        frag = arm_id.encode() + _u32(gen)
        for t in tags:
            frag += _u32(t)
        if viol != 0:
            # rollback journal; keep prior blob conceptually
            pass
        else:
            journal = journal + frag

        witness = arm_id.encode()
        for t in tags:
            witness += _u32(t)
        for k in edge_keys:
            witness += _f64(res[k])

        seal_payload = b"seal/t1:" + witness + hashlib.sha256(journal).digest()[:8]
        row_seal = hashlib.sha256(seal_payload).hexdigest()
        seal_mark = 1 if len(row_seal) == 64 else 0

        payload = arm_id.encode()
        for t in tags:
            payload += _u32(t)
        for k in edge_keys:
            payload += _f64(res[k])
        payload += hashlib.sha256(journal).digest()[:8]
        digest_hex = hashlib.sha256(payload).hexdigest()

        out_rows.append(
            {
                "arm_id": arm_id,
                "digest_hex": digest_hex,
                "viol_n": viol,
                "eps_used": tol,
                "seal_mark": seal_mark,
                "stage_mark": 1,
            }
        )

    total_viol = sum(r["viol_n"] for r in out_rows)
    sorted_rows = sorted(out_rows, key=lambda r: r["arm_id"])
    blob = b"".join(r["digest_hex"].encode() for r in sorted_rows) + _u32(total_viol)
    seal_hex = hashlib.sha256(blob).hexdigest()
    closed = 1
    for r in out_rows:
        if r["viol_n"] != 0 or r["seal_mark"] != 1:
            closed = 0
            break

    return {
        "schema_ver": 1,
        "rows": out_rows,
        "util_max": util_max,
        "seal_hex": seal_hex,
        "closed_n": closed,
    }


@pytest.fixture(scope="module")
def bundle():
    _rebuild_and_emit()
    return _load_bundle()


@pytest.fixture(scope="module")
def ref():
    return reference_bundle()


def test_b01_field_rows(bundle):
    """YAML field layout matches t_policy schema."""
    assert bundle.get("schema_ver") == 1
    rows = bundle.get("rows")
    assert isinstance(rows, list) and len(rows) >= 5
    needed = {"arm_id", "digest_hex", "viol_n", "eps_used", "seal_mark", "stage_mark"}
    for row in rows:
        assert needed <= set(row)
    assert "util_max" in bundle and "seal_hex" in bundle and "closed_n" in bundle
    ids = [r["arm_id"] for r in rows]
    assert ids[0] == "train_a" and "host_b" in ids
    for pid, _ in _load_perms():
        assert pid in ids


def test_b02_hex_lane(bundle, ref):
    """Digest hex length, charset, and formula agreement."""
    for row, rr in zip(bundle["rows"], ref["rows"], strict=True):
        assert isinstance(row["digest_hex"], str)
        assert len(row["digest_hex"]) == 64
        assert row["digest_hex"] == row["digest_hex"].lower()
        int(row["digest_hex"], 16)
        assert row["digest_hex"] == rr["digest_hex"]
    assert len(bundle["seal_hex"]) == 64
    assert bundle["seal_hex"] == ref["seal_hex"]


def test_b03_hostile_suite(bundle, ref):
    """Stress-arm corpus satisfies zero-violation obligation."""
    by_id = {r["arm_id"]: r for r in bundle["rows"]}
    ref_by = {r["arm_id"]: r for r in ref["rows"]}
    assert by_id["host_b"]["viol_n"] == ref_by["host_b"]["viol_n"]
    assert by_id["host_b"]["digest_hex"] == ref_by["host_b"]["digest_hex"]
    assert bundle["closed_n"] == ref["closed_n"]
    assert round(float(bundle["util_max"]), 12) == round(float(ref["util_max"]), 12)


def test_b04_reord_table(bundle, ref):
    """Every perm_tbl ordering survives closed algebra."""
    by_id = {r["arm_id"]: r for r in bundle["rows"]}
    ref_by = {r["arm_id"]: r for r in ref["rows"]}
    for pid, _ in _load_perms():
        assert by_id[pid]["viol_n"] == ref_by[pid]["viol_n"]
        assert by_id[pid]["digest_hex"] == ref_by[pid]["digest_hex"]
        assert by_id[pid]["seal_mark"] == ref_by[pid]["seal_mark"]


def test_b05_early_bypass(bundle, ref):
    """Stage gauges alone must not count as success."""
    for row, rr in zip(bundle["rows"], ref["rows"], strict=True):
        assert row["stage_mark"] == rr["stage_mark"]
        assert row["seal_mark"] == rr["seal_mark"]
        assert len(row["digest_hex"]) == 64
    assert bundle["closed_n"] == ref["closed_n"]
    assert bundle["seal_hex"] == ref["seal_hex"]


def test_b06_double_emit(bundle):
    """Consecutive hv7 emits are byte-identical when sealed."""
    first = OUT.read_bytes()
    _rebuild_and_emit()
    second = OUT.read_bytes()
    assert first == second


def test_b07_flip_mat(bundle, ref):
    """Matrix encoding participates in arm digests."""
    for row, rr in zip(bundle["rows"], ref["rows"], strict=True):
        assert row["digest_hex"] == rr["digest_hex"]
    assert bundle["closed_n"] == ref["closed_n"]


def test_b08_flip_mass(bundle, ref):
    """Mass fold residuals and eps band match policy."""
    for row, rr in zip(bundle["rows"], ref["rows"], strict=True):
        assert row["viol_n"] == rr["viol_n"]
        assert float(row["eps_used"]) == float(rr["eps_used"])
    assert round(float(bundle["util_max"]), 12) == round(float(ref["util_max"]), 12)
    assert bundle["rows"][0]["digest_hex"] == ref["rows"][0]["digest_hex"]


def test_b09_flip_rec(bundle, ref):
    """Independent certificate replay seal marks hold."""
    for row, rr in zip(bundle["rows"], ref["rows"], strict=True):
        assert row["seal_mark"] == rr["seal_mark"]
    assert bundle["seal_hex"] == ref["seal_hex"]


def test_b10_zero_ops(bundle, ref):
    """Empty-ops path cannot satisfy closed algebra alone."""
    assert bundle["closed_n"] == ref["closed_n"]
    assert [r["viol_n"] for r in bundle["rows"]] == [r["viol_n"] for r in ref["rows"]]
    assert bundle["seal_hex"] == ref["seal_hex"]


def test_b11_wipe_emit(bundle, ref):
    """Wiped output regenerates through hv7."""
    if OUT.exists():
        OUT.unlink()
    _rebuild_and_emit()
    got = _load_bundle()
    assert got["closed_n"] == ref["closed_n"]
    assert got["seal_hex"] == ref["seal_hex"]
    assert [r["digest_hex"] for r in got["rows"]] == [r["digest_hex"] for r in ref["rows"]]


def test_b12_tol_band(bundle, ref):
    """Residual and probability tolerance class from t_policy."""
    for row, rr in zip(bundle["rows"], ref["rows"], strict=True):
        assert float(row["eps_used"]) == float(rr["eps_used"])
        assert row["viol_n"] == rr["viol_n"]
    assert round(float(bundle["util_max"]), 12) == round(float(ref["util_max"]), 12)
    assert bundle["closed_n"] == ref["closed_n"]
