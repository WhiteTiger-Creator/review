"""Behavioral checks for the meshgate reconcile command."""

from __future__ import annotations

import json
import random
import subprocess
import tempfile
import uuid
from collections.abc import Iterable
from pathlib import Path

from mesh_reference import get_sig, reconcile_mesh

ROOT = (
    Path("/app")
    if Path("/app/cmd/meshgate/main.go").exists()
    else Path(__file__).parents[1].resolve()
)
MAIN = ROOT / "cmd/meshgate/main.go"
DEFAULT_DATA = ROOT / "data"
DEFAULT_POLICY = ROOT / "spec/mesh_policy.json"
DEFAULT_OUT = ROOT / "output/posture.json"


def run_reconcile(data: Path, policy: Path, output: Path, use_alias: bool = False) -> subprocess.CompletedProcess:
    """Execute meshgate against given paths."""
    data_flag = "--data" if use_alias else "--data-root"
    cmd = [
        "go",
        "run",
        str(MAIN),
        "reconcile",
        data_flag,
        str(data),
        "--policy",
        str(policy),
        "--output",
        str(output),
    ]
    return subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, check=False)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_gateway_segments(root: Path, gateway_id: str, segments: Iterable[Iterable[dict]]) -> None:
    """Write one gateway's telemetry segments, filling signatures unless overridden."""
    gw_dir = root / gateway_id
    gw_dir.mkdir(parents=True, exist_ok=True)

    for idx, records in enumerate(segments, start=1):
        encoded = []
        for rec in records:
            row = dict(rec)
            if "sig" not in row:
                row["sig"] = get_sig(
                    gateway_id,
                    row["seq"],
                    row["ts"],
                    row["unit_id"],
                    row["op"],
                    row.get("metric", ""),
                    row.get("val"),
                    row.get("offset"),
                )
            encoded.append(json.dumps(row))

        (gw_dir / f"seg_{idx:03d}.jsonl").write_text("\n".join(encoded) + "\n", encoding="utf-8")


def build_seeded_matrix_fixture(root: Path, seed: int) -> tuple[Path, Path, dict]:
    """Create a deterministic multi-gateway fixture with interacting runtime behavior."""
    gw_root = root / "gw"
    policy_file = root / "topo.json"

    base = 18.0 + (seed * 0.37)
    policy = {
        "bound_nodes": [{"left": "alpha", "right": "beta"}],
        "home_sites": {
            "alpha": ["gw_A", "gw_B"],
            "beta": ["gw_A"],
            "rogue": ["gw_A"],
        },
        "sync_metrics": ["temp"],
    }
    policy_file.write_text(json.dumps(policy), encoding="utf-8")

    write_gateway_segments(
        gw_root,
        "gw_A",
        [
            [
                {"seq": 1, "ts": "2026-07-04T12:00:00Z", "unit_id": "alpha", "op": "BOOT"},
                {"seq": 2, "ts": "2026-07-04T12:00:01Z", "unit_id": "beta", "op": "BOOT"},
                {"seq": 3, "ts": "2026-07-04T12:00:02Z", "unit_id": "alpha", "op": "BATCH_BEGIN"},
            ],
            [
                {"seq": 4, "ts": "2026-07-04T12:00:03Z", "unit_id": "alpha", "op": "TELEMETRY", "metric": "temp", "val": round(base + 0.25, 2)},
                {"seq": 5, "ts": "2026-07-04T12:00:04Z", "unit_id": "alpha", "op": "TUNE", "offset": round(0.2 + (seed * 0.05), 2)},
                {"seq": 6, "ts": "2026-07-04T12:00:05Z", "unit_id": "alpha", "op": "TELEMETRY", "metric": "temp", "val": round(base + 1.15, 2)},
                {"seq": 7, "ts": "2026-07-04T12:00:06Z", "unit_id": "alpha", "op": "BATCH_COMMIT"},
                {"seq": 8, "ts": "2026-07-04T12:00:07Z", "unit_id": "beta", "op": "PING"},
                {"seq": 9, "ts": "2026-07-04T12:00:08Z", "unit_id": "beta", "op": "SHUTDOWN"},
                {"seq": 10, "ts": "2026-07-04T12:00:09Z", "unit_id": "beta", "op": "PING"},
            ],
        ],
    )

    write_gateway_segments(
        gw_root,
        "gw_B",
        [
            [
                {"seq": 1, "ts": "2026-07-04T12:01:00Z", "unit_id": "alpha", "op": "BOOT"},
                {"seq": 2, "ts": "2026-07-04T12:01:01Z", "unit_id": "alpha", "op": "TELEMETRY", "metric": "temp", "val": round(base + 1.55, 2)},
                {"seq": 3, "ts": "2026-07-04T12:01:02Z", "unit_id": "alpha", "op": "PING"},
            ]
        ],
    )

    write_gateway_segments(
        gw_root,
        "gw_C",
        [
            [
                {"seq": 1, "ts": "2026-07-04T12:02:00Z", "unit_id": "rogue", "op": "BOOT"},
                {"seq": 2, "ts": "2026-07-04T12:02:01Z", "unit_id": "rogue", "op": "TUNE", "offset": round(0.4 + (seed * 0.03), 2)},
                {"seq": 3, "ts": "2026-07-04T12:02:02Z", "unit_id": "rogue", "op": "BATCH_BEGIN"},
            ],
            [
                {"seq": 4, "ts": "2026-07-04T12:02:03Z", "unit_id": "rogue", "op": "TELEMETRY", "metric": "temp", "val": round(base + 4.05, 2)},
                {"seq": 5, "ts": "2026-07-04T12:02:04Z", "unit_id": "rogue", "op": "BATCH_ABORT"},
                {"seq": 6, "ts": "2026-07-04T12:02:05Z", "unit_id": "rogue", "op": "TELEMETRY", "metric": "temp", "val": round(base + 4.55, 2)},
            ],
        ],
    )

    return gw_root, policy_file, policy


# --- Tests ---


def test_reconcile_produces_output():
    """meshgate reconcile must exit 0 and write posture JSON to /app/output/posture.json."""
    if DEFAULT_OUT.exists():
        DEFAULT_OUT.unlink()

    result = run_reconcile(DEFAULT_DATA, DEFAULT_POLICY, DEFAULT_OUT)
    assert result.returncode == 0, f"meshgate failed: {result.stderr}"
    assert DEFAULT_OUT.is_file(), "posture.json was not created"


def test_default_matches_reference():
    """Default shipped site streams must produce posture JSON exactly matching the reference model."""
    expected = reconcile_mesh(DEFAULT_DATA, load_json(DEFAULT_POLICY))

    out_file = DEFAULT_OUT
    run_reconcile(DEFAULT_DATA, DEFAULT_POLICY, out_file)
    actual = load_json(out_file)

    assert actual == expected


def test_empty_lists_are_arrays_not_null():
    """Empty input must serialize gateways, drift_events, units, and metrics as [] rather than null."""
    with tempfile.TemporaryDirectory() as tmp:
        empty_dir = Path(tmp) / "empty_data"
        empty_dir.mkdir()
        out_file = Path(tmp) / "out.json"

        policy_file = Path(tmp) / "topo.json"
        policy_file.write_text(json.dumps({
            "bound_nodes": [],
            "home_sites": {},
            "sync_metrics": []
        }))

        res = run_reconcile(empty_dir, policy_file, out_file)
        assert res.returncode == 0

        raw = out_file.read_text(encoding="utf-8")
        assert "null" not in raw, "Serialized JSON contains 'null' values indicating uninitialized slices"

        data = json.loads(raw)
        assert data["gateways"] == []
        assert data["drift_events"] == []
        assert data["recoverable"] is True


def test_custom_output_and_root_flags():
    """Verify --output and --data/--data-root paths are respected."""
    with tempfile.TemporaryDirectory() as tmp:
        out_root = Path(tmp) / "out"
        out_root.mkdir()
        out_file = out_root / "report.json"

        res1 = run_reconcile(DEFAULT_DATA, DEFAULT_POLICY, out_file, use_alias=False)
        assert res1.returncode == 0
        assert out_file.is_file()
        assert load_json(out_file) == load_json(DEFAULT_OUT)

        out_file.unlink()

        res2 = run_reconcile(DEFAULT_DATA, DEFAULT_POLICY, out_file, use_alias=True)
        assert res2.returncode == 0
        assert out_file.is_file()
        assert load_json(out_file) == load_json(DEFAULT_OUT)


def test_signature_mismatch_validation():
    """Bad signature records make a gateway unrecoverable and emit bad_signature findings."""
    with tempfile.TemporaryDirectory() as tmp:
        gw_root = Path(tmp) / "gw"
        dev_dir = gw_root / "gw_sig_error"
        dev_dir.mkdir(parents=True)
        out_file = Path(tmp) / "out.json"
        policy_file = Path(tmp) / "topo.json"

        policy_file.write_text(json.dumps({
            "bound_nodes": [],
            "home_sites": {},
            "sync_metrics": []
        }))

        expected_sig = get_sig("gw_sig_error", 1, "2026-07-04T12:00:00Z", "unit-01", "BOOT")
        line1 = json.dumps({"seq": 1, "ts": "2026-07-04T12:00:00Z", "unit_id": "unit-01", "op": "BOOT", "sig": expected_sig})
        line2 = json.dumps({"seq": 2, "ts": "2026-07-04T12:00:05Z", "unit_id": "unit-01", "op": "TELEMETRY", "metric": "temp", "val": 22.5, "sig": "bad_sig_field_value_goes_here"})

        (dev_dir / "seg_001.jsonl").write_text(f"{line1}\n{line2}\n", encoding="utf-8")

        res = run_reconcile(gw_root, policy_file, out_file)
        assert res.returncode == 0
        data = load_json(out_file)

        assert data["recoverable"] is False
        gw_report = next(g for g in data["gateways"] if g["gateway_id"] == "gw_sig_error")
        assert gw_report["recoverable"] is False
        assert len(gw_report["units"]) == 0

        sig_events = [v for v in data["drift_events"] if v["reason"] == "bad_signature"]
        assert len(sig_events) == 1
        assert sig_events[0]["seq"] == 2
        assert sig_events[0]["detail"] == "signature hash mismatch"


def test_transaction_staging_and_aborts():
    """Verify that batch actions inside BEGIN...ABORT/COMMIT are staged and rolled back or applied accordingly."""
    with tempfile.TemporaryDirectory() as tmp:
        gw_root = Path(tmp) / "gw"
        dev_dir = gw_root / "gw_tx"
        dev_dir.mkdir(parents=True)
        out_file = Path(tmp) / "out.json"
        policy_file = Path(tmp) / "topo.json"

        policy_file.write_text(json.dumps({"bound_nodes": [], "home_sites": {}, "sync_metrics": []}))

        lines = [
            {"seq": 1, "ts": "2026-07-04T12:00:00Z", "unit_id": "dev1", "op": "BOOT"},
            {"seq": 2, "ts": "2026-07-04T12:00:01Z", "unit_id": "dev1", "op": "BATCH_BEGIN"},
            {"seq": 3, "ts": "2026-07-04T12:00:02Z", "unit_id": "dev1", "op": "TELEMETRY", "metric": "temp", "val": 10.0},
            {"seq": 4, "ts": "2026-07-04T12:00:03Z", "unit_id": "dev1", "op": "BATCH_ABORT"},
            {"seq": 5, "ts": "2026-07-04T12:00:04Z", "unit_id": "dev1", "op": "BATCH_BEGIN"},
            {"seq": 6, "ts": "2026-07-04T12:00:05Z", "unit_id": "dev1", "op": "TELEMETRY", "metric": "temp", "val": 15.0},
            {"seq": 7, "ts": "2026-07-04T12:00:06Z", "unit_id": "dev1", "op": "TUNE", "offset": 1.0},
            {"seq": 8, "ts": "2026-07-04T12:00:07Z", "unit_id": "dev1", "op": "TELEMETRY", "metric": "temp", "val": 17.0},
            {"seq": 9, "ts": "2026-07-04T12:00:08Z", "unit_id": "dev1", "op": "BATCH_COMMIT"}
        ]

        json_lines = []
        for x in lines:
            x["sig"] = get_sig("gw_tx", x["seq"], x["ts"], x["unit_id"], x["op"], x.get("metric", ""), x.get("val"), x.get("offset"))
            json_lines.append(json.dumps(x))
        (dev_dir / "seg_001.jsonl").write_text("\n".join(json_lines) + "\n", encoding="utf-8")

        res = run_reconcile(gw_root, policy_file, out_file)
        assert res.returncode == 0
        data = load_json(out_file)

        assert data["recoverable"] is True
        gw_data = data["gateways"][0]
        dev_data = gw_data["units"][0]
        temp_metric = dev_data["metrics"][0]

        assert temp_metric["count"] == 2
        assert temp_metric["min"] == 15.0
        assert temp_metric["max"] == 18.0
        assert temp_metric["average"] == 16.5


def test_cross_segment_batch_violation_aborts_state_and_turns_late_commit_into_orphan():
    """A batch can span files, but any in-batch violation must discard staged state immediately."""
    with tempfile.TemporaryDirectory() as tmp:
        gw_root = Path(tmp) / "gw"
        out_file = Path(tmp) / "out.json"
        policy_file = Path(tmp) / "topo.json"

        policy_file.write_text(json.dumps({"bound_nodes": [], "home_sites": {}, "sync_metrics": []}), encoding="utf-8")

        write_gateway_segments(
            gw_root,
            "gw_cross_batch",
            [
                [
                    {"seq": 1, "ts": "2026-07-04T12:00:00Z", "unit_id": "dev1", "op": "BOOT"},
                    {"seq": 2, "ts": "2026-07-04T12:00:01Z", "unit_id": "dev1", "op": "BATCH_BEGIN"},
                    {"seq": 3, "ts": "2026-07-04T12:00:02Z", "unit_id": "dev1", "op": "TELEMETRY", "metric": "temp", "val": 40.0},
                ],
                [
                    {"seq": 4, "ts": "2026-07-04T12:00:03Z", "unit_id": "dev1", "op": "NOPE"},
                    {"seq": 5, "ts": "2026-07-04T12:00:04Z", "unit_id": "dev1", "op": "BATCH_COMMIT"},
                    {"seq": 6, "ts": "2026-07-04T12:00:05Z", "unit_id": "dev1", "op": "TELEMETRY", "metric": "temp", "val": 50.0},
                ],
            ],
        )

        expected = reconcile_mesh(gw_root, json.loads(policy_file.read_text(encoding="utf-8")))
        res = run_reconcile(gw_root, policy_file, out_file)
        assert res.returncode == 0, f"meshgate failed: {res.stderr}"
        actual = load_json(out_file)

        assert actual == expected

        reasons = [v["reason"] for v in actual["drift_events"]]
        assert reasons == ["unknown_op_or_metric", "orphan_batch"]

        temp_metric = actual["gateways"][0]["units"][0]["metrics"][0]
        assert temp_metric["count"] == 1
        assert temp_metric["min"] == 50.0
        assert temp_metric["max"] == 50.0
        assert temp_metric["average"] == 50.0


def test_policy_bound_nodes_validation():
    """Verify bound_nodes co-location: per gateway, if either bound unit is active, both must be active on that same gateway."""
    with tempfile.TemporaryDirectory() as tmp:
        gw_root = Path(tmp) / "gw"
        dev_dir = gw_root / "gw_coloc"
        dev_dir.mkdir(parents=True)
        out_file = Path(tmp) / "out.json"
        policy_file = Path(tmp) / "topo.json"

        policy_file.write_text(json.dumps({
            "bound_nodes": [{"left": "temp-1", "right": "hum-1"}],
            "home_sites": {},
            "sync_metrics": []
        }))

        lines = [
            {"seq": 1, "ts": "2026-07-04T12:00:00Z", "unit_id": "temp-1", "op": "BOOT"}
        ]
        json_lines = []
        for x in lines:
            x["sig"] = get_sig("gw_coloc", x["seq"], x["ts"], x["unit_id"], x["op"])
            json_lines.append(json.dumps(x))
        (dev_dir / "seg_001.jsonl").write_text("\n".join(json_lines) + "\n", encoding="utf-8")

        res = run_reconcile(gw_root, policy_file, out_file)
        assert res.returncode == 0
        data = load_json(out_file)

        assert data["recoverable"] is True
        binding_events = [v for v in data["drift_events"] if v["reason"] == "binding_breach"]
        assert len(binding_events) == 1
        assert binding_events[0]["seq"] == 0
        assert binding_events[0]["detail"] == "binding broken: temp-1 and hum-1 not co-present"


def test_policy_home_sites_validation():
    """Verify home_sites restriction rules."""
    with tempfile.TemporaryDirectory() as tmp:
        gw_root = Path(tmp) / "gw"
        dev_dir = gw_root / "gw_unauth"
        dev_dir.mkdir(parents=True)
        out_file = Path(tmp) / "out.json"
        policy_file = Path(tmp) / "topo.json"

        policy_file.write_text(json.dumps({
            "bound_nodes": [],
            "home_sites": {"unit-1": ["gw_allowed"]},
            "sync_metrics": []
        }))

        lines = [
            {"seq": 1, "ts": "2026-07-04T12:00:00Z", "unit_id": "unit-1", "op": "BOOT"}
        ]
        json_lines = []
        for x in lines:
            x["sig"] = get_sig("gw_unauth", x["seq"], x["ts"], x["unit_id"], x["op"])
            json_lines.append(json.dumps(x))
        (dev_dir / "seg_001.jsonl").write_text("\n".join(json_lines) + "\n", encoding="utf-8")

        res = run_reconcile(gw_root, policy_file, out_file)
        assert res.returncode == 0
        data = load_json(out_file)

        site_events = [v for v in data["drift_events"] if v["reason"] == "site_forbidden"]
        assert len(site_events) == 1
        assert site_events[0]["unit_id"] == "unit-1"
        assert site_events[0]["detail"] == "unit unit-1 seen on foreign site gw_unauth"


def test_policy_sync_metrics_validation():
    """Verify sync_metrics average limits comparisons."""
    with tempfile.TemporaryDirectory() as tmp:
        gw_root = Path(tmp) / "gw"
        gw1 = gw_root / "gw1"
        gw2 = gw_root / "gw2"
        gw1.mkdir(parents=True)
        gw2.mkdir(parents=True)
        out_file = Path(tmp) / "out.json"
        policy_file = Path(tmp) / "topo.json"

        policy_file.write_text(json.dumps({
            "bound_nodes": [],
            "home_sites": {},
            "sync_metrics": ["temp"]
        }))

        lines1 = [
            {"seq": 1, "ts": "2026-07-04T12:00:00Z", "unit_id": "d1", "op": "BOOT"},
            {"seq": 2, "ts": "2026-07-04T12:00:01Z", "unit_id": "d1", "op": "TELEMETRY", "metric": "temp", "val": 20.0}
        ]
        lines2 = [
            {"seq": 1, "ts": "2026-07-04T12:00:00Z", "unit_id": "d2", "op": "BOOT"},
            {"seq": 2, "ts": "2026-07-04T12:00:01Z", "unit_id": "d2", "op": "TELEMETRY", "metric": "temp", "val": 20.10}
        ]

        json_lines1 = [json.dumps(dict(x, sig=get_sig("gw1", x["seq"], x["ts"], x["unit_id"], x["op"], x.get("metric", ""), x.get("val")))) for x in lines1]
        json_lines2 = [json.dumps(dict(x, sig=get_sig("gw2", x["seq"], x["ts"], x["unit_id"], x["op"], x.get("metric", ""), x.get("val")))) for x in lines2]

        (gw1 / "seg_001.jsonl").write_text("\n".join(json_lines1) + "\n", encoding="utf-8")
        (gw2 / "seg_001.jsonl").write_text("\n".join(json_lines2) + "\n", encoding="utf-8")

        res = run_reconcile(gw_root, policy_file, out_file)
        assert res.returncode == 0
        data = load_json(out_file)

        sync_events = [v for v in data["drift_events"] if v["reason"] == "sync_skew"]
        assert len(sync_events) == 1
        assert sync_events[0]["detail"] == "sync metric skew: temp exceeds tolerance"


def test_dynamic_random_run_matches_reference():
    """Generate dynamic sensor data, evaluate the reference model, and verify the command matches."""
    seed = str(uuid.uuid4())
    random.seed(seed)

    gw_names = ["gw_A", "gw_B"]
    units = ["dev_X", "dev_Y"]

    with tempfile.TemporaryDirectory() as tmp:
        gw_root = Path(tmp) / "gw"
        out_file = Path(tmp) / "out.json"
        policy_file = Path(tmp) / "topo.json"

        policy_dict = {
            "bound_nodes": [{"left": "dev_X", "right": "dev_Y"}],
            "home_sites": {"dev_X": ["gw_A", "gw_B"], "dev_Y": ["gw_A", "gw_B"]},
            "sync_metrics": ["temp"]
        }
        policy_file.write_text(json.dumps(policy_dict))

        for gw in gw_names:
            gw_dir = gw_root / gw
            gw_dir.mkdir(parents=True)

            lines = []
            lines.append({"seq": 1, "ts": "2026-07-04T12:00:00Z", "unit_id": "dev_X", "op": "BOOT"})
            lines.append({"seq": 2, "ts": "2026-07-04T12:00:05Z", "unit_id": "dev_Y", "op": "BOOT"})

            seq = 3
            ts_offset = 10
            for _ in range(5):
                unit = random.choice(units)
                op = random.choices(["TELEMETRY", "TUNE", "PING"], weights=[70, 15, 15])[0]

                r = {
                    "seq": seq,
                    "ts": f"2026-07-04T12:00:{ts_offset:02d}Z",
                    "unit_id": unit,
                    "op": op
                }
                if op == "TELEMETRY":
                    r["metric"] = "temp"
                    r["val"] = round(random.uniform(15.0, 25.0), 2)
                elif op == "TUNE":
                    r["offset"] = round(random.uniform(-1.0, 1.0), 2)

                lines.append(r)
                seq += 1
                ts_offset += 5

            json_lines = []
            for r in lines:
                r["sig"] = get_sig(gw, r["seq"], r["ts"], r["unit_id"], r["op"], r.get("metric", ""), r.get("val"), r.get("offset"))
                json_lines.append(json.dumps(r))

            (gw_dir / "seg_001.jsonl").write_text("\n".join(json_lines) + "\n", encoding="utf-8")

        expected = reconcile_mesh(gw_root, policy_dict)

        res = run_reconcile(gw_root, policy_file, out_file)
        assert res.returncode == 0, f"meshgate failed: {res.stderr}"
        actual = load_json(out_file)

        assert actual == expected


def test_seeded_reference_matrix_matches_reference():
    """Multiple deterministic fixtures should match the independent reference model exactly."""
    for seed in range(5):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            gw_root, policy_file, policy = build_seeded_matrix_fixture(tmp_root, seed)
            out_file = tmp_root / "out.json"

            expected = reconcile_mesh(gw_root, policy)
            res = run_reconcile(gw_root, policy_file, out_file)
            assert res.returncode == 0, f"seed {seed} failed: {res.stderr}"
            actual = load_json(out_file)

            assert actual == expected

            reasons = {v["reason"] for v in actual["drift_events"]}
            assert "stale_unit_op" in reasons
            assert "binding_breach" in reasons
            assert "site_forbidden" in reasons
            assert "sync_skew" in reasons


def test_tool_is_rerunnable():
    """Running tool multiple times outputs identical consistent result."""
    with tempfile.TemporaryDirectory() as tmp:
        out1 = Path(tmp) / "out1.json"
        out2 = Path(tmp) / "out2.json"

        run_reconcile(DEFAULT_DATA, DEFAULT_POLICY, out1)
        run_reconcile(DEFAULT_DATA, DEFAULT_POLICY, out2)

        assert load_json(out1) == load_json(out2)
