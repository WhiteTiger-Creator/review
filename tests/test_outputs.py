"""Verifier for culvert intake pipeline."""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/app/environment/support")
from spectrum_model import (
    affinity,
    group_digest_for,
    laplacian,
    parse_rank_yaml,
    smallest_eigs,
)

APP = Path("/app")
ENV = APP / "environment"
FIXTURES = ENV / "fixtures"
OUTPUT = APP / "output" / "culvert_rank.yaml"
REPLAY = "/app/environment/scripts/replay.sh"


def _phase_b(samples: list[list[float]]) -> tuple[list[float], list[float], int]:
    dim = len(samples[0])
    norms = [math.sqrt(sum(v * v for v in row)) for row in samples]
    avg = sum(norms) / len(norms)
    if avg < 1e-9:
        avg = 1.0
    shift = [0.0] * dim
    scale = [avg] * dim
    median = sorted(norms)[len(norms) // 2]
    above = sum(1 for norm in norms if norm > median)
    bucket = above % 3
    return shift, scale, bucket


def _apply_window(
    points: list[list[float]], shift: list[float], scale: list[float]
) -> list[list[float]]:
    return [
        [(points[i][d] - shift[d]) / scale[d] for d in range(len(points[i]))]
        for i in range(len(points))
    ]


def _op_a(spectrum: list[float], bucket: int) -> tuple[int, float]:
    best_k = 1
    best_gap = -1.0
    for k in range(1, len(spectrum)):
        gap = spectrum[k] - spectrum[k - 1]
        if gap > best_gap:
            best_gap = gap
            best_k = k
    upper = len(spectrum) - 1
    adj = min(max(best_k + bucket, 1), upper)
    return adj, best_gap


def _reconcile(nodes: list[dict]) -> tuple[list[str], str]:
    rows = [(n["id"], math.sqrt(sum(v * v for v in n["features"]))) for n in nodes]
    ids = [r[0] for r in rows]
    weights = [r[1] for r in rows]
    order = sorted(range(len(rows)), key=lambda i: (-weights[i], ids[i]))
    rank = [ids[i] for i in order]
    return rank, group_digest_for(rank)


def _reference_run(payload: dict) -> dict:
    nodes = payload["nodes"]
    raw = [n["features"] for n in nodes]
    shift, scale, bucket = _phase_b(raw)
    normed = _apply_window(raw, shift, scale)
    spectrum = smallest_eigs(laplacian(affinity(normed)), min(4, len(nodes)))
    k, span = _op_a(spectrum, bucket)
    rank, digest = _reconcile(nodes)
    return {
        "profile": "culvert-inv-1",
        "partition_count": k,
        "rank_order": rank,
        "spectral_span": round(span, 3),
        "group_digest": digest,
    }


def _load_rank_record(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    return parse_rank_yaml(text)


def _run_culvert_replay(case_path: Path) -> dict:
    if OUTPUT.exists():
        OUTPUT.unlink()
    subprocess.run(
        ["bash", REPLAY, str(case_path)],
        check=True,
        cwd=str(APP),
    )
    assert OUTPUT.exists(), "pipeline did not write culvert_rank.yaml"
    return _load_rank_record(OUTPUT)


def _load_fixture_case(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def _rotate_feature_points(points: list[list[float]], theta: float) -> list[list[float]]:
    c = math.cos(theta)
    s = math.sin(theta)
    out = []
    for x, y in points:
        out.append([x * c - y * s, x * s + y * c])
    return out


def _scale_feature_points(points: list[list[float]], factor: float) -> list[list[float]]:
    return [[v * factor for v in row] for row in points]


def _write_temp_case(nodes: list[dict], marks: list[str], tmp_dir: Path, name: str = "case") -> Path:
    path = tmp_dir / f"{name}.json"
    path.write_text(json.dumps({"name": name, "nodes": nodes, "marks": marks}), encoding="utf-8")
    return path


def _assert_stable_fields(left: dict, right: dict) -> None:
    assert left["partition_count"] == right["partition_count"]
    assert left["rank_order"] == right["rank_order"]
    assert left["group_digest"] == right["group_digest"]
    assert left["spectral_span"] == right["spectral_span"]


TRANSFORM_BASES = [
    [
        {"id": "u0", "features": [1.2, -0.4]},
        {"id": "u1", "features": [-0.8, 2.1]},
        {"id": "u2", "features": [2.4, 0.3]},
        {"id": "u3", "features": [-1.5, -1.1]},
        {"id": "u4", "features": [0.2, 2.8]},
    ],
    [
        {"id": "u0", "features": [-2.0, 0.5]},
        {"id": "u1", "features": [0.4, 1.9]},
        {"id": "u2", "features": [1.7, -1.2]},
        {"id": "u3", "features": [-0.6, -2.2]},
        {"id": "u4", "features": [2.5, 0.9]},
    ],
    [
        {"id": "u0", "features": [0.9, 1.4]},
        {"id": "u1", "features": [-1.8, 0.2]},
        {"id": "u2", "features": [2.2, -0.7]},
        {"id": "u3", "features": [-0.3, -1.6]},
        {"id": "u4", "features": [1.1, 2.3]},
    ],
    [
        {"id": "w0", "features": [3.1, -2.4]},
        {"id": "w1", "features": [-2.7, 0.2]},
        {"id": "w2", "features": [0.4, 3.3]},
        {"id": "w3", "features": [-1.2, -2.9]},
        {"id": "w4", "features": [2.0, 1.1]},
        {"id": "w5", "features": [-0.5, 0.8]},
    ],
]

ROT_ANGLES = [0.7, 1.1, 1.6, 2.3]
SCALE_FACTORS = [1.8, 2.4, 3.0, 0.35]


class TestCulvertPipeline:
    def test_anchor_fixture_fields(self) -> None:
        """Primary visible case matches the replay contract fields."""
        expected = _reference_run(_load_fixture_case("f01"))
        actual = _run_culvert_replay(FIXTURES / "f01.json")
        assert actual["profile"] == expected["profile"]
        assert actual["partition_count"] == expected["partition_count"]
        assert actual["rank_order"] == expected["rank_order"]
        assert actual["group_digest"] == expected["group_digest"]
        assert actual["spectral_span"] == expected["spectral_span"]

    def test_marked_metamorphic_convergence(self) -> None:
        """Bundled 0417 fixtures match the anchor on stable fields including digest and span."""
        primary = _run_culvert_replay(FIXTURES / "f01.json")
        for name in ("f02", "f03"):
            actual = _run_culvert_replay(FIXTURES / f"{name}.json")
            _assert_stable_fields(actual, primary)

    def test_rotation_rank_stability(self, tmp_path: Path) -> None:
        """Rotated 0417 cases preserve stable fields versus the unrotated sibling."""
        for idx, nodes in enumerate(TRANSFORM_BASES):
            angle = ROT_ANGLES[idx % len(ROT_ANGLES)]
            base_case = _write_temp_case(nodes, [], tmp_path, f"rot_base_{idx}")
            rotated_nodes = [
                {"id": n["id"], "features": _rotate_feature_points([n["features"]], angle)[0]}
                for n in nodes
            ]
            rot_case = _write_temp_case(rotated_nodes, ["0417-rot"], tmp_path, f"rot_case_{idx}")
            base = _run_culvert_replay(base_case)
            actual = _run_culvert_replay(rot_case)
            _assert_stable_fields(actual, base)

    def test_scaling_rank_stability(self, tmp_path: Path) -> None:
        """Scaled 0417 cases preserve stable fields versus the unscaled sibling."""
        for idx, nodes in enumerate(TRANSFORM_BASES):
            factor = SCALE_FACTORS[idx % len(SCALE_FACTORS)]
            base_case = _write_temp_case(nodes, [], tmp_path, f"scale_base_{idx}")
            scaled_nodes = [
                {"id": n["id"], "features": _scale_feature_points([n["features"]], factor)[0]}
                for n in nodes
            ]
            scale_case = _write_temp_case(scaled_nodes, ["0417-scale"], tmp_path, f"scale_case_{idx}")
            base = _run_culvert_replay(base_case)
            actual = _run_culvert_replay(scale_case)
            _assert_stable_fields(actual, base)

    def test_composed_similarity_stability(self, tmp_path: Path) -> None:
        """Rotation followed by isotropic scale preserves stable fields on 0417 marks."""
        for idx, nodes in enumerate(TRANSFORM_BASES[:3]):
            angle = ROT_ANGLES[idx]
            factor = SCALE_FACTORS[idx]
            base_case = _write_temp_case(nodes, [], tmp_path, f"comp_base_{idx}")
            transformed = []
            for n in nodes:
                rotated = _rotate_feature_points([n["features"]], angle)[0]
                scaled = _scale_feature_points([rotated], factor)[0]
                transformed.append({"id": n["id"], "features": scaled})
            comp_case = _write_temp_case(
                transformed,
                ["0417-rot", "0417-scale"],
                tmp_path,
                f"comp_case_{idx}",
            )
            base = _run_culvert_replay(base_case)
            actual = _run_culvert_replay(comp_case)
            _assert_stable_fields(actual, base)

    def test_window_bucket_partition_count(self, tmp_path: Path) -> None:
        """Partition count follows window-conditioned spectrum selection with a real bucket effect."""
        payload = _load_fixture_case("f03")
        raw = [n["features"] for n in payload["nodes"]]
        shift, scale, bucket = _phase_b(raw)
        assert bucket > 0
        normed = _apply_window(raw, shift, scale)
        spectrum = smallest_eigs(laplacian(affinity(normed)), min(4, len(payload["nodes"])))
        with_bucket, _ = _op_a(spectrum, bucket)
        without_bucket, _ = _op_a(spectrum, 0)
        assert with_bucket != without_bucket
        actual = _run_culvert_replay(FIXTURES / "f03.json")
        assert actual["partition_count"] == with_bucket

        alt_nodes = [
            {"id": "p0", "features": [4.2, 0.1]},
            {"id": "p1", "features": [4.0, -0.2]},
            {"id": "p2", "features": [-3.8, 0.3]},
            {"id": "p3", "features": [-4.1, -0.1]},
            {"id": "p4", "features": [0.2, 0.05]},
        ]
        alt_raw = [n["features"] for n in alt_nodes]
        shift_a, scale_a, bucket_a = _phase_b(alt_raw)
        assert bucket_a > 0
        normed_a = _apply_window(alt_raw, shift_a, scale_a)
        spectrum_a = smallest_eigs(laplacian(affinity(normed_a)), min(4, len(alt_nodes)))
        with_a, _ = _op_a(spectrum_a, bucket_a)
        without_a, _ = _op_a(spectrum_a, 0)
        assert with_a != without_a
        alt_case = _write_temp_case(alt_nodes, ["0417-scale"], tmp_path, "alt_bucket")
        alt_actual = _run_culvert_replay(alt_case)
        assert alt_actual["partition_count"] == with_a

    def test_mark_neutrality(self, tmp_path: Path) -> None:
        """Identical features with and without 0417 marks must emit the same ranking fields."""
        nodes = TRANSFORM_BASES[1]
        plain = _write_temp_case(nodes, [], tmp_path, "plain")
        marked = _write_temp_case(nodes, ["0417-rot"], tmp_path, "marked")
        _assert_stable_fields(_run_culvert_replay(marked), _run_culvert_replay(plain))

    def test_pipeline_regenerates_output(self, tmp_path: Path) -> None:
        """Modifying node features and replaying changes digest and rank_order via live execution."""
        first = _run_culvert_replay(FIXTURES / "f01.json")
        payload = _load_fixture_case("f01")
        payload["nodes"][0]["features"] = [9.5, -1.2]
        case = _write_temp_case(payload["nodes"], payload.get("marks", []), tmp_path, "regen")
        second = _run_culvert_replay(case)
        assert second["group_digest"] != first["group_digest"]
        assert second["rank_order"] != first["rank_order"]
        expected = _reference_run(
            {"name": "regen", "nodes": payload["nodes"], "marks": payload.get("marks", [])}
        )
        assert second["rank_order"] == expected["rank_order"]
        assert second["group_digest"] == expected["group_digest"]
        assert second["partition_count"] == expected["partition_count"]
