"""
Verifier for the symlink topology evaluator.
Validates /app/output/health_report.json against the contract specification.
"""

import json
import os
import subprocess


def load_report():
    """Load the health report from the expected output path."""
    with open("/app/output/health_report.json") as f:
        return json.load(f)


def test_binary_compiles():
    """Verify the symlink-health binary compiles without errors."""
    subprocess.run(["make", "clean"], capture_output=True, cwd="/app", timeout=30)
    result = subprocess.run(
        ["make"], capture_output=True, text=True, cwd="/app", timeout=120
    )
    assert result.returncode == 0, f"Build failed: {result.stderr[:500]}"


def test_report_exists():
    """Verify the health report was generated at the expected path."""
    assert os.path.exists("/app/output/health_report.json"), "Report not found"


def test_report_top_level_keys():
    """Verify report has all required top-level keys per output schema."""
    report = load_report()
    for key in ["summary", "overall_status", "entries", "segments", "metadata"]:
        assert key in report, f"Missing top-level key: {key}"


def test_total_entries():
    """Verify all 31 symlinks from the manifest are reported."""
    report = load_report()
    assert len(report["entries"]) == 31, (
        f"Expected 31 entries, got {len(report['entries'])}"
    )


def test_summary_total():
    """Verify summary.total equals the manifest entry count."""
    report = load_report()
    assert report["summary"]["total"] == 31


def test_summary_healthy():
    """Verify healthy count reflects entries passing all classification checks."""
    report = load_report()
    assert report["summary"]["healthy"] == 25, (
        f"Expected 25 healthy, got {report['summary']['healthy']}"
    )


def test_summary_dangling():
    """Verify dangling count matches entries with unresolvable targets."""
    report = load_report()
    assert report["summary"]["dangling"] == 2, (
        f"Expected 2 dangling, got {report['summary']['dangling']}"
    )


def test_summary_cycles():
    """Verify cycle count includes all entries whose resolution detects a revisit."""
    report = load_report()
    assert report["summary"]["cycles"] == 4, (
        f"Expected 4 cycles, got {report['summary']['cycles']}"
    )


def test_summary_no_excessive_depth():
    """Verify no entries exceed the configured max_chain_depth of 8."""
    report = load_report()
    assert report["summary"]["excessive_depth"] == 0


def test_summary_no_permission_fault():
    """Verify no permission faults with the configured mask 510."""
    report = load_report()
    assert report["summary"]["permission_fault"] == 0


def test_overall_status():
    """Verify overall_status is critical per V2 (worst segment) and V4 (count > 4)."""
    report = load_report()
    assert report["overall_status"] == "critical", (
        f"Expected 'critical', got '{report['overall_status']}'"
    )


def test_dangling_entries_identified():
    """Verify the two dangling symlinks are correctly classified."""
    report = load_report()
    entries_map = {e["path"]: e for e in report["entries"]}
    assert entries_map["/srv/app/tmp/orphan1"]["status"] == "dangling"
    assert entries_map["/srv/app/tmp/orphan2"]["status"] == "dangling"


def test_cycle_entries_ring():
    """Verify all three cycle ring members are classified as cycle."""
    report = load_report()
    entries_map = {e["path"]: e for e in report["entries"]}
    for p in ["/srv/app/cycle/a", "/srv/app/cycle/b", "/srv/app/cycle/c"]:
        assert entries_map[p]["status"] == "cycle", (
            f"{p} should be cycle, got {entries_map[p]['status']}"
        )


def test_watcher_classified_cycle():
    """Verify watcher entry (chains into cycle) is classified as cycle per R3."""
    report = load_report()
    entries_map = {e["path"]: e for e in report["entries"]}
    assert entries_map["/srv/app/cycle/watcher"]["status"] == "cycle", (
        "watcher's resolution detects a revisit, must be classified as cycle"
    )


def test_session_healthy():
    """Verify session entry is healthy (target IS a tracked symlink per C4)."""
    report = load_report()
    entries_map = {e["path"]: e for e in report["entries"]}
    assert entries_map["/srv/app/tmp/session"]["status"] == "healthy", (
        "session target (orphan1) is tracked, so session is not dangling"
    )


def test_deep_chains_healthy():
    """Verify deep chain entries l1-l6 are all healthy with max_depth=8."""
    report = load_report()
    entries_map = {e["path"]: e for e in report["entries"]}
    for i in range(1, 7):
        p = f"/srv/app/lib/deep/l{i}"
        assert entries_map[p]["status"] == "healthy", (
            f"{p} should be healthy, got {entries_map[p]['status']}"
        )


def test_chain_depths_deep():
    """Verify chain depth computation for the 6-hop chain."""
    report = load_report()
    entries_map = {e["path"]: e for e in report["entries"]}
    expected = {
        "/srv/app/lib/deep/l1": 6,
        "/srv/app/lib/deep/l2": 5,
        "/srv/app/lib/deep/l3": 4,
        "/srv/app/lib/deep/l4": 3,
        "/srv/app/lib/deep/l5": 2,
        "/srv/app/lib/deep/l6": 1,
    }
    for path, depth in expected.items():
        assert entries_map[path]["chain_depth"] == depth, (
            f"{path} expected depth {depth}, got {entries_map[path]['chain_depth']}"
        )


def test_cycle_chain_depth():
    """Verify cycle entries have chain_depth equal to ring size (3) per R3."""
    report = load_report()
    entries_map = {e["path"]: e for e in report["entries"]}
    for p in ["/srv/app/cycle/a", "/srv/app/cycle/b", "/srv/app/cycle/c",
              "/srv/app/cycle/watcher"]:
        assert entries_map[p]["chain_depth"] == 3, (
            f"{p} cycle depth should be 3 (ring size), got {entries_map[p]['chain_depth']}"
        )


def test_dangling_chain_depth():
    """Verify dangling entries have chain_depth of 0 per R2."""
    report = load_report()
    entries_map = {e["path"]: e for e in report["entries"]}
    assert entries_map["/srv/app/tmp/orphan1"]["chain_depth"] == 0
    assert entries_map["/srv/app/tmp/orphan2"]["chain_depth"] == 0


def test_cycle_final_target():
    """Verify cycle entries record the back-edge target per R4."""
    report = load_report()
    entries_map = {e["path"]: e for e in report["entries"]}
    assert entries_map["/srv/app/cycle/a"]["final_target"] == "/srv/app/cycle/a"
    assert entries_map["/srv/app/cycle/b"]["final_target"] == "/srv/app/cycle/b"
    assert entries_map["/srv/app/cycle/c"]["final_target"] == "/srv/app/cycle/c"
    assert entries_map["/srv/app/cycle/watcher"]["final_target"] == "/srv/app/cycle/a"


def test_permission_entries_healthy():
    """Verify permission-set entries are healthy with mask 510 (ignores bit 0)."""
    report = load_report()
    entries_map = {e["path"]: e for e in report["entries"]}
    for p in ["/srv/app/opt/perm1", "/srv/app/opt/perm2", "/srv/app/opt/perm3"]:
        assert entries_map[p]["status"] == "healthy", (
            f"{p} should be healthy with mask 510, got {entries_map[p]['status']}"
        )


def test_session_taint_propagation():
    """Verify session gets taint_dangling via forward propagation to orphan1."""
    report = load_report()
    entries_map = {e["path"]: e for e in report["entries"]}
    taints = entries_map["/srv/app/tmp/session"]["taints"]
    assert "taint_dangling" in taints, (
        f"session should have taint_dangling, got {taints}"
    )


def test_dangling_self_taint():
    """Verify dangling entries carry taint_dangling (self-taint per P5)."""
    report = load_report()
    entries_map = {e["path"]: e for e in report["entries"]}
    for p in ["/srv/app/tmp/orphan1", "/srv/app/tmp/orphan2"]:
        assert "taint_dangling" in entries_map[p]["taints"], (
            f"{p} should self-taint with taint_dangling"
        )


def test_cycle_self_taint():
    """Verify cycle entries carry taint_cycle (self-taint per P5)."""
    report = load_report()
    entries_map = {e["path"]: e for e in report["entries"]}
    for p in ["/srv/app/cycle/a", "/srv/app/cycle/b",
              "/srv/app/cycle/c", "/srv/app/cycle/watcher"]:
        assert "taint_cycle" in entries_map[p]["taints"], (
            f"{p} should have taint_cycle"
        )


def test_healthy_no_taints():
    """Verify healthy entries outside fault segments have no taints."""
    report = load_report()
    entries_map = {e["path"]: e for e in report["entries"]}
    clean_paths = [
        "/srv/app/lib/libcore.so",
        "/srv/app/lib/deep/l1",
        "/srv/app/share/docs",
        "/srv/app/opt/perm1",
    ]
    for p in clean_paths:
        assert entries_map[p]["taints"] == [], (
            f"{p} should have empty taints, got {entries_map[p]['taints']}"
        )


def test_no_cross_segment_propagation():
    """Verify taints do not propagate across segment boundaries per P4."""
    report = load_report()
    # All segment 1-5 and 8 entries must have no taints regardless of
    # what happens in segments 6 and 7
    for e in report["entries"]:
        if e["segment_group"] in [1, 2, 3, 4, 5, 8]:
            assert e["taints"] == [], (
                f"{e['path']} (seg {e['segment_group']}) should have no taints"
            )


def test_scoring_healthy_prio1():
    """Verify healthy priority-1 entries score 10.0 (no taint, weight 1.0)."""
    report = load_report()
    entries_map = {e["path"]: e for e in report["entries"]}
    assert entries_map["/srv/app/lib/libcore.so"]["health_score"] == 10.0
    assert entries_map["/srv/app/lib/deep/l1"]["health_score"] == 10.0


def test_scoring_healthy_prio2():
    """Verify healthy priority-2 entries score 8.0 (weight 0.8)."""
    report = load_report()
    entries_map = {e["path"]: e for e in report["entries"]}
    assert entries_map["/srv/app/lib/libutil.so"]["health_score"] == 8.0
    assert entries_map["/srv/app/data/cache"]["health_score"] == 8.0


def test_scoring_healthy_prio3():
    """Verify healthy priority-3 entries score 5.0 (weight 0.5)."""
    report = load_report()
    entries_map = {e["path"]: e for e in report["entries"]}
    assert entries_map["/srv/app/etc/fallback"]["health_score"] == 5.0


def test_scoring_session_tainted():
    """Verify session entry score reflects taint penalty and priority weight."""
    report = load_report()
    entries_map = {e["path"]: e for e in report["entries"]}
    # healthy base=10, taint_dangling penalty=-1, net=9, weight=0.8 -> 7.2
    assert abs(entries_map["/srv/app/tmp/session"]["health_score"] - 7.2) < 0.01, (
        f"session score should be 7.2, got "
        f"{entries_map['/srv/app/tmp/session']['health_score']}"
    )


def test_scoring_dangling_tainted():
    """Verify dangling entries score with base, self-taint penalty, and weight."""
    report = load_report()
    entries_map = {e["path"]: e for e in report["entries"]}
    # dangling base=5, taint_dangling=-1, net=4, weight=0.5 -> 2.0
    assert abs(entries_map["/srv/app/tmp/orphan1"]["health_score"] - 2.0) < 0.01
    assert abs(entries_map["/srv/app/tmp/orphan2"]["health_score"] - 2.0) < 0.01


def test_scoring_cycle_prio1():
    """Verify cycle priority-1 entries score with base and self-taint."""
    report = load_report()
    entries_map = {e["path"]: e for e in report["entries"]}
    # cycle base=2, taint_cycle=-1.5, net=0.5, weight=1.0 -> 0.5
    for p in ["/srv/app/cycle/a", "/srv/app/cycle/b", "/srv/app/cycle/c"]:
        assert abs(entries_map[p]["health_score"] - 0.5) < 0.01, (
            f"{p} score should be 0.5, got {entries_map[p]['health_score']}"
        )


def test_scoring_watcher_cycle_prio2():
    """Verify watcher (cycle, prio 2) scores with priority weight 0.8."""
    report = load_report()
    entries_map = {e["path"]: e for e in report["entries"]}
    # cycle base=2, taint_cycle=-1.5, net=0.5, weight=0.8 -> 0.4
    assert abs(entries_map["/srv/app/cycle/watcher"]["health_score"] - 0.4) < 0.01, (
        f"watcher score should be 0.4, got "
        f"{entries_map['/srv/app/cycle/watcher']['health_score']}"
    )


def test_segment_count():
    """Verify all 8 segments are reported."""
    report = load_report()
    assert len(report["segments"]) == 8


def test_segment_ids_ordered():
    """Verify segments are sorted by ID ascending."""
    report = load_report()
    ids = [s["id"] for s in report["segments"]]
    assert ids == list(range(1, 9))


def test_segment_1_aggregate():
    """Verify segment 1 (all healthy, mixed priority) has score 1.0."""
    report = load_report()
    seg_map = {s["id"]: s for s in report["segments"]}
    assert abs(seg_map[1]["aggregate_score"] - 1.0) < 0.001


def test_segment_2_aggregate():
    """Verify segment 2 (all healthy, includes prio 3) has score 1.0."""
    report = load_report()
    seg_map = {s["id"]: s for s in report["segments"]}
    # sum_scores = 10+10+5=25, sum_max = 10+10+5=25, ratio=1.0
    assert abs(seg_map[2]["aggregate_score"] - 1.0) < 0.001


def test_segment_6_aggregate():
    """Verify transient segment score with tainted and dangling entries."""
    report = load_report()
    seg_map = {s["id"]: s for s in report["segments"]}
    # sum_scores = 7.2+2.0+2.0=11.2, sum_max = 8+5+5=18, ratio=0.6222
    expected = 11.2 / 18.0
    assert abs(seg_map[6]["aggregate_score"] - expected) < 0.001, (
        f"Segment 6 score should be ~{expected:.4f}, "
        f"got {seg_map[6]['aggregate_score']}"
    )


def test_segment_7_aggregate():
    """Verify circular-deps segment score with 4 cycle entries."""
    report = load_report()
    seg_map = {s["id"]: s for s in report["segments"]}
    # sum_scores = 0.5+0.5+0.5+0.4=1.9, sum_max = 10+10+10+8=38, ratio=0.05
    expected = 1.9 / 38.0
    assert abs(seg_map[7]["aggregate_score"] - expected) < 0.001, (
        f"Segment 7 score should be ~{expected:.4f}, "
        f"got {seg_map[7]['aggregate_score']}"
    )


def test_segment_healthy_verdicts():
    """Verify segments scoring >= threshold have verdict healthy."""
    report = load_report()
    seg_map = {s["id"]: s for s in report["segments"]}
    for seg_id in [1, 2, 3, 4, 5, 8]:
        assert seg_map[seg_id]["verdict"] == "healthy", (
            f"Segment {seg_id} should be healthy, got {seg_map[seg_id]['verdict']}"
        )


def test_segment_6_verdict():
    """Verify segment 6 is degraded (score between threshold*0.5 and threshold)."""
    report = load_report()
    seg_map = {s["id"]: s for s in report["segments"]}
    assert seg_map[6]["verdict"] == "degraded"


def test_segment_7_verdict():
    """Verify segment 7 is critical (score below threshold*0.5=0.375)."""
    report = load_report()
    seg_map = {s["id"]: s for s in report["segments"]}
    assert seg_map[7]["verdict"] == "critical"


def test_fleet_score_weighted():
    """Verify fleet_score is entry-count-weighted average of segment scores."""
    report = load_report()
    seg_map = {s["id"]: s for s in report["segments"]}
    numerator = sum(seg_map[i]["aggregate_score"] * seg_map[i]["total"]
                    for i in range(1, 9))
    denominator = sum(seg_map[i]["total"] for i in range(1, 9))
    expected = numerator / denominator
    assert abs(report["summary"]["fleet_score"] - expected) < 0.001, (
        f"Fleet score mismatch: expected {expected:.4f}, "
        f"got {report['summary']['fleet_score']}"
    )


def test_fleet_score_value():
    """Verify fleet_score computed value is approximately 0.8409."""
    report = load_report()
    # (1.0*4 + 1.0*3 + 1.0*3 + 1.0*2 + 1.0*6 + (11.2/18)*3 + (1.9/38)*4 + 1.0*6)/31
    seg6_score = 11.2 / 18.0
    seg7_score = 1.9 / 38.0
    expected = (4 + 3 + 3 + 2 + 6 + seg6_score * 3 + seg7_score * 4 + 6) / 31.0
    assert abs(report["summary"]["fleet_score"] - expected) < 0.001, (
        f"Expected fleet_score ~{expected:.4f}, "
        f"got {report['summary']['fleet_score']}"
    )


def test_segment_healthy_unhealthy_counts():
    """Verify segment healthy/unhealthy counts reflect classification only."""
    report = load_report()
    seg_map = {s["id"]: s for s in report["segments"]}
    # Segment 6: 1 healthy (session), 2 unhealthy (dangling)
    assert seg_map[6]["healthy"] == 1
    assert seg_map[6]["unhealthy"] == 2
    # Segment 7: 0 healthy, 4 unhealthy (all cycle)
    assert seg_map[7]["healthy"] == 0
    assert seg_map[7]["unhealthy"] == 4
    # Segment 1: 4 healthy, 0 unhealthy
    assert seg_map[1]["healthy"] == 4
    assert seg_map[1]["unhealthy"] == 0


def test_metadata_config_source():
    """Verify config_source reflects the authoritative config file."""
    report = load_report()
    assert report["metadata"]["config_source"] == "health_config.json"


def test_metadata_max_depth():
    """Verify metadata max_chain_depth from config."""
    report = load_report()
    assert report["metadata"]["max_chain_depth"] == 8


def test_metadata_permission_mask():
    """Verify metadata permission_mask from config."""
    report = load_report()
    assert report["metadata"]["permission_mask"] == 510


def test_metadata_score_threshold():
    """Verify metadata score_threshold from config."""
    report = load_report()
    assert abs(report["metadata"]["score_threshold"] - 0.75) < 0.001


def test_metadata_scoring_mode():
    """Verify metadata scoring_mode from config."""
    report = load_report()
    assert report["metadata"]["scoring_mode"] == "weighted"


def test_metadata_timestamp():
    """Verify metadata timestamp from manifest scan_timestamp."""
    report = load_report()
    assert report["metadata"]["timestamp"] == "2024-09-15T00:00:00Z"


def test_entries_preserve_manifest_order():
    """Verify entries array follows manifest order, not resolution order."""
    report = load_report()
    paths = [e["path"] for e in report["entries"]]
    assert paths[0] == "/srv/app/lib/libcore.so"
    assert paths[3] == "/srv/app/bin/app"
    assert paths[12] == "/srv/app/lib/deep/l1"
    assert paths[18] == "/srv/app/tmp/session"
    assert paths[-1] == "/srv/app/opt/ref3"


def test_entries_have_taints_field():
    """Verify every entry includes the taints array field."""
    report = load_report()
    for e in report["entries"]:
        assert "taints" in e, f"Entry {e['path']} missing taints field"
        assert isinstance(e["taints"], list), (
            f"Entry {e['path']} taints should be array"
        )


def test_health_score_precision():
    """Verify health_score is rounded to 2 decimal places."""
    report = load_report()
    for e in report["entries"]:
        score = e["health_score"]
        rounded = round(score, 2)
        assert abs(score - rounded) < 0.001, (
            f"{e['path']} score {score} not rounded to 2 decimals"
        )


def test_aggregate_score_precision():
    """Verify segment aggregate_score is rounded to 4 decimal places."""
    report = load_report()
    for s in report["segments"]:
        score = s["aggregate_score"]
        rounded = round(score, 4)
        assert abs(score - rounded) < 0.00001, (
            f"Segment {s['id']} aggregate {score} not rounded to 4 decimals"
        )


def test_binary_exits_zero():
    """Verify the binary exits with code 0 on valid input."""
    result = subprocess.run(
        ["/app/bin/symlink-health", "--manifest", "/app/data/manifest.json",
         "--config", "/app/config", "--output", "/tmp/exit_test.json"],
        capture_output=True, timeout=30
    )
    assert result.returncode == 0


def test_deterministic_output():
    """Verify running twice produces identical output."""
    for i in range(2):
        subprocess.run(
            ["/app/bin/symlink-health", "--manifest", "/app/data/manifest.json",
             "--config", "/app/config", "--output", f"/tmp/det_{i}.json"],
            capture_output=True, timeout=30
        )
    with open("/tmp/det_0.json") as f:
        r1 = json.load(f)
    with open("/tmp/det_1.json") as f:
        r2 = json.load(f)
    assert r1 == r2, "Non-deterministic output"


def test_summary_consistency():
    """Verify summary counts match actual entry status distribution."""
    report = load_report()
    counts = {}
    for e in report["entries"]:
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    assert counts.get("healthy", 0) == report["summary"]["healthy"]
    assert counts.get("dangling", 0) == report["summary"]["dangling"]
    assert counts.get("cycle", 0) == report["summary"]["cycles"]
    assert counts.get("excessive_depth", 0) == report["summary"]["excessive_depth"]
    assert counts.get("permission_fault", 0) == report["summary"]["permission_fault"]
