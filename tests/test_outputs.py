import hashlib
import os
import shutil
import subprocess
from pathlib import Path

GOVERN = Path(os.environ.get("CEPH_GOVERN", "/usr/local/bin/ceph-govern"))
POLICY = Path(
    os.environ.get(
        "CEPH_POLICY", "/app/work/ceph/bin/backfill-governance"
    )
)
SCENARIOS = Path(
    os.environ.get("CEPH_SCENARIOS", "/opt/ceph-governance/scenarios")
)
DOCS = Path(os.environ.get("CEPH_DOCS", "/opt/ceph-governance/docs"))
INTEGRITY = Path(
    os.environ.get(
        "CEPH_INTEGRITY", "/opt/ceph-governance/integrity.sha256"
    )
)
SOURCE_MARKER = Path("/opt/ceph-governance/ceph-govern.source.sha256")
SOURCE_IDENTITY_SHA256 = (
    "ccddd3d0fbe913e097631c1b22f7b0f28af96fcff58a83062aa7d3bd8d105310"
)
PROTECTED_DIRECTORIES = (
    Path("/opt/ceph-governance"),
    DOCS,
    SCENARIOS,
)
CEPH_CONFIG = Path(
    os.environ.get("CEPH_CONFIG", "/app/work/ceph/etc/ceph.conf")
)


def _read_fields(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, value = line.split("=", 1)
        fields[key] = value
    return fields


def _apply(
    tmp_path: Path, name: str, policy: Path = POLICY
) -> dict[str, str]:
    output = tmp_path / f"{Path(name).stem}.state"
    result = subprocess.run(
        [str(GOVERN), "apply", str(SCENARIOS / name), str(policy), str(output)],
        check=False,
        capture_output=True,
        text=True,
        timeout=8,
    )
    assert result.returncode == 0, result.stderr
    state = _read_fields(output)
    assert state["valid"] == "true"
    return state


def _mutated_cluster(
    tmp_path: Path, source: str, changes: dict[str, str], name: str
) -> Path:
    fields = _read_fields(SCENARIOS / source)
    fields.update(changes)
    path = tmp_path / name
    path.write_text(
        "".join(f"{key}={value}\n" for key, value in fields.items()),
        encoding="utf-8",
    )
    return path


def _apply_path(
    tmp_path: Path, cluster: Path, policy: Path = POLICY
) -> dict[str, str]:
    output = tmp_path / f"{cluster.stem}.state"
    result = subprocess.run(
        [str(GOVERN), "apply", str(cluster), str(policy), str(output)],
        check=False,
        capture_output=True,
        text=True,
        timeout=8,
    )
    assert result.returncode == 0, result.stderr
    return _read_fields(output)


def _variant_policy(
    tmp_path: Path,
    name: str,
    replacements: dict[str, tuple[str, str]],
) -> Path:
    root = tmp_path / name
    binary = root / "bin/backfill-governance"
    binary.parent.mkdir(parents=True)
    shutil.copy2(POLICY, binary)
    shutil.copytree(CEPH_CONFIG.parent, root / "etc")
    for filename, replacement in replacements.items():
        path = root / "etc" / filename
        path.write_text(
            path.read_text(encoding="utf-8").replace(*replacement),
            encoding="utf-8",
        )
    return binary


def _recorded_digest(path: Path) -> str:
    for line in INTEGRITY.read_text(encoding="utf-8").splitlines():
        digest, recorded = line.split(maxsplit=1)
        if Path(recorded.lstrip("*")).resolve() == path.resolve():
            return digest
    raise AssertionError(f"missing integrity record for {path}")


def _assert_digest(path: Path) -> None:
    assert hashlib.sha256(path.read_bytes()).hexdigest() == _recorded_digest(path)


def _assert_protected_manifest() -> None:
    assert SOURCE_MARKER.read_text(encoding="utf-8").strip() == (
        SOURCE_IDENTITY_SHA256
    )
    protected_files = [GOVERN, INTEGRITY, SOURCE_MARKER]
    for line in INTEGRITY.read_text(encoding="utf-8").splitlines():
        digest, recorded = line.split(maxsplit=1)
        path = Path(recorded)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        protected_files.append(path)
    for path in (*PROTECTED_DIRECTORIES, *protected_files):
        metadata = path.stat()
        assert metadata.st_uid == 0
        assert metadata.st_mode & 0o222 == 0


def test_ceph_govern_binary_integrity_is_preserved() -> None:
    _assert_protected_manifest()
    _assert_digest(GOVERN)
    assert os.access(GOVERN, os.X_OK)
    assert not Path("/tmp/ceph_govern.cpp").exists()


def test_ceph_backfill_catalog_integrity_is_preserved() -> None:
    _assert_digest(SCENARIOS / "catalog.txt")
    assert len((SCENARIOS / "catalog.txt").read_text().splitlines()) == 12


def test_ceph_fullness_document_integrity_is_preserved() -> None:
    _assert_digest(DOCS / "fullness-policy.txt")
    _assert_digest(DOCS / "failure-domains.txt")
    _assert_digest(DOCS / "maintenance-baseline.txt")


def test_ceph_native_configuration_matches_governance_controls() -> None:
    text = CEPH_CONFIG.read_text(encoding="utf-8")
    assert "[osd]" in text
    assert "osd_max_backfills = 1" in text
    assert "osd_recovery_op_priority = 2" in text
    assert "osd_recovery_sleep = 0.05" in text
    assert _read_fields(CEPH_CONFIG.parent / "flags.conf") == {
        "maintenance_flag": "nobackfill",
        "clear_only_owned": "true",
    }


def test_ceph_safe_direct_window_completes_backfill(tmp_path: Path) -> None:
    state = _apply(tmp_path, "safe-direct.cluster")
    assert state["status"] == "complete"
    assert state["dest_used"] == "700"
    assert state["moves"] == "1"
    assert state["flags"] == ""


def test_ceph_projected_full_destination_pauses_before_change(
    tmp_path: Path,
) -> None:
    state = _apply(tmp_path, "projected-full.cluster")
    assert state["status"] == "paused"
    assert state["dest_used"] == "850"
    assert state["moves"] == "0"
    assert "fullness-gate" in state["trace"]


def test_ceph_duplicate_rack_destination_blocks_replica_collapse(
    tmp_path: Path,
) -> None:
    state = _apply(tmp_path, "duplicate-rack.cluster")
    assert state["status"] == "paused"
    assert state["weight"] == "1.000000"
    assert "failure-domain" in state["trace"]


def test_ceph_degraded_health_holds_recovery_controls(tmp_path: Path) -> None:
    state = _apply(tmp_path, "degraded-health.cluster")
    assert state["status"] == "paused"
    assert state["max_backfills"] == "-1"
    assert "degraded-health" in state["trace"]


def test_ceph_stale_epoch_prevents_osd_reweight(tmp_path: Path) -> None:
    state = _apply(tmp_path, "stale-epoch.cluster")
    assert state["status"] == "paused"
    assert state["asserted_epoch"] == "44"
    assert state["epoch"] == "45"
    assert "reweight" not in state["trace"]


def test_ceph_quiet_window_uses_parallel_backfill_budget(tmp_path: Path) -> None:
    state = _apply(tmp_path, "quiet-recovery.cluster")
    assert state["status"] == "complete"
    assert state["max_backfills"] == "3"
    assert state["recovery_priority"] == "5"


def test_ceph_busy_window_uses_client_safe_backfill_budget(
    tmp_path: Path,
) -> None:
    state = _apply(tmp_path, "busy-recovery.cluster")
    assert state["status"] == "complete"
    assert state["max_backfills"] == "1"
    assert state["recovery_priority"] == "2"


def test_ceph_large_reweight_is_staged_without_migration(tmp_path: Path) -> None:
    state = _apply(tmp_path, "stage-reweight.cluster")
    assert state["status"] == "staged"
    assert state["weight"] == "0.850000"
    assert state["checkpoint"] == "reweighted"
    assert state["moves"] == "0"
    assert state["owned_flags"] == "nobackfill"


def test_ceph_reweighted_restart_resumes_at_movement(tmp_path: Path) -> None:
    state = _apply(tmp_path, "resume-reweighted.cluster")
    assert state["status"] == "complete"
    assert state["moves"] == "1"
    assert state["dest_used"] == "590"
    assert "reweight" not in state["trace"]


def test_ceph_migrated_restart_composite_only_cleans_owned_flag(
    tmp_path: Path,
) -> None:
    state = _apply(tmp_path, "resume-migrated.cluster")
    assert state["status"] == "complete"
    assert state["moves"] == "0"
    assert state["dest_used"] == "590"
    assert state["owned_flags"] == ""
    assert "move " not in state["trace"]

    cluster = _mutated_cluster(
        tmp_path,
        "resume-migrated.cluster",
        {
            "id": "migrated-under-pressure",
            "dest_used": "950",
            "dest_rack": "rack-ab",
        },
        "migrated-under-pressure.cluster",
    )
    pressured = _apply_path(tmp_path, cluster)
    assert pressured["status"] == "complete"
    assert pressured["moves"] == "0"
    assert pressured["dest_used"] == "950"
    assert pressured["owned_flags"] == ""


def test_ceph_foreign_nobackfill_flag_remains_untouched(tmp_path: Path) -> None:
    state = _apply(tmp_path, "foreign-flag.cluster")
    assert state["status"] == "paused"
    assert state["flags"] == "nobackfill"
    assert state["owned_flags"] == ""
    assert "clear" not in state["trace"]


def test_ceph_nearfull_with_backfill_headroom_can_progress(
    tmp_path: Path,
) -> None:
    state = _apply(tmp_path, "nearfull-headroom.cluster")
    assert state["status"] == "complete"
    assert state["dest_used"] == "880"
    assert state["moves"] == "1"


def test_ceph_fullness_opposite_one_byte_below_boundary_moves(
    tmp_path: Path,
) -> None:
    cluster = _mutated_cluster(
        tmp_path,
        "projected-full.cluster",
        {"dest_used": "849", "move_bytes": "50", "id": "below-boundary"},
        "below-boundary.cluster",
    )
    state = _apply_path(tmp_path, cluster)
    assert state["status"] == "complete"
    assert state["dest_used"] == "899"


def test_ceph_fullness_opposite_exact_boundary_holds(tmp_path: Path) -> None:
    cluster = _mutated_cluster(
        tmp_path,
        "projected-full.cluster",
        {"dest_used": "849", "move_bytes": "51", "id": "exact-boundary"},
        "exact-boundary.cluster",
    )
    state = _apply_path(tmp_path, cluster)
    assert state["status"] == "paused"
    assert state["dest_used"] == "849"


def test_ceph_failure_domain_opposite_unique_rack_moves(tmp_path: Path) -> None:
    cluster = _mutated_cluster(
        tmp_path,
        "duplicate-rack.cluster",
        {"dest_rack": "rack-d", "id": "unique-rack"},
        "unique-rack.cluster",
    )
    state = _apply_path(tmp_path, cluster)
    assert state["status"] == "complete"
    assert state["moves"] == "1"


def test_ceph_failure_domain_opposite_duplicate_rack_holds(
    tmp_path: Path,
) -> None:
    cluster = _mutated_cluster(
        tmp_path,
        "safe-direct.cluster",
        {"dest_rack": "rack-b", "id": "hidden-duplicate"},
        "hidden-duplicate.cluster",
    )
    state = _apply_path(tmp_path, cluster)
    assert state["status"] == "paused"
    assert "failure-domain" in state["trace"]


def test_ceph_epoch_refresh_mutation_allows_same_backfill(tmp_path: Path) -> None:
    cluster = _mutated_cluster(
        tmp_path,
        "stale-epoch.cluster",
        {"observed_epoch": "45", "id": "refreshed-epoch"},
        "refreshed-epoch.cluster",
    )
    state = _apply_path(tmp_path, cluster)
    assert state["status"] == "complete"
    assert state["moves"] == "1"


def test_ceph_capacity_scaling_metamorphic_invariance(tmp_path: Path) -> None:
    base = _apply(tmp_path, "safe-direct.cluster")
    cluster = _mutated_cluster(
        tmp_path,
        "safe-direct.cluster",
        {
            "dest_used": "6200",
            "dest_capacity": "10000",
            "move_bytes": "800",
            "id": "scaled-capacity",
        },
        "scaled-capacity.cluster",
    )
    scaled = _apply_path(tmp_path, cluster)
    assert base["status"] == scaled["status"] == "complete"
    assert int(scaled["dest_used"]) == int(base["dest_used"]) * 10


def test_ceph_identifier_rename_metamorphic_invariance(tmp_path: Path) -> None:
    cluster = _mutated_cluster(
        tmp_path,
        "safe-direct.cluster",
        {
            "source_osd": "osd.403",
            "dest_osd": "osd.911",
            "source_host": "alpha-storage",
            "dest_host": "delta-storage",
            "source_rack": "zone-alpha",
            "dest_rack": "zone-delta",
            "replica_hosts": "beta-storage,gamma-storage",
            "replica_racks": "zone-beta,zone-gamma",
            "id": "renamed-topology",
        },
        "renamed-topology.cluster",
    )
    state = _apply_path(tmp_path, cluster)
    assert state["status"] == "complete"
    assert "reweight osd.403" in state["trace"]


def test_ceph_topology_reorder_metamorphic_invariance(tmp_path: Path) -> None:
    first = _apply(tmp_path, "safe-direct.cluster")
    cluster = _mutated_cluster(
        tmp_path,
        "safe-direct.cluster",
        {
            "replica_hosts": "storage-c,storage-b",
            "replica_racks": "rack-c,rack-b",
            "id": "reordered-replicas",
        },
        "reordered-replicas.cluster",
    )
    second = _apply_path(tmp_path, cluster)
    assert first["status"] == second["status"]
    assert first["dest_used"] == second["dest_used"]


def test_ceph_reweight_step_uses_stricter_cluster_limit(tmp_path: Path) -> None:
    cluster = _mutated_cluster(
        tmp_path,
        "stage-reweight.cluster",
        {"max_step": "0.05", "id": "small-step"},
        "small-step.cluster",
    )
    state = _apply_path(tmp_path, cluster)
    assert state["status"] == "staged"
    assert state["weight"] == "0.950000"


def test_ceph_client_iops_threshold_switches_recovery_tuning(
    tmp_path: Path,
) -> None:
    cluster = _mutated_cluster(
        tmp_path,
        "quiet-recovery.cluster",
        {"client_iops": "8000", "id": "iops-threshold"},
        "iops-threshold.cluster",
    )
    state = _apply_path(tmp_path, cluster)
    assert state["max_backfills"] == "1"
    assert state["recovery_priority"] == "2"


def test_ceph_queue_threshold_switches_recovery_tuning(tmp_path: Path) -> None:
    cluster = _mutated_cluster(
        tmp_path,
        "quiet-recovery.cluster",
        {"recovery_queue": "24", "id": "queue-threshold"},
        "queue-threshold.cluster",
    )
    state = _apply_path(tmp_path, cluster)
    assert state["max_backfills"] == "1"
    assert state["recovery_priority"] == "2"


def test_ceph_owned_flag_composite_is_cleared_after_safe_resume(
    tmp_path: Path,
) -> None:
    cluster = _mutated_cluster(
        tmp_path,
        "resume-reweighted.cluster",
        {"external_flags": "noout", "id": "owned-plus-foreign"},
        "owned-plus-foreign.cluster",
    )
    state = _apply_path(tmp_path, cluster)
    assert state["status"] == "complete"
    assert state["flags"] == "noout"
    assert state["owned_flags"] == ""


def test_ceph_pressure_health_composite_preserves_all_state(
    tmp_path: Path,
) -> None:
    cluster = _mutated_cluster(
        tmp_path,
        "projected-full.cluster",
        {
            "health": "degraded",
            "client_iops": "9900",
            "external_flags": "noout",
            "id": "multiple-blockers",
        },
        "multiple-blockers.cluster",
    )
    state = _apply_path(tmp_path, cluster)
    assert state["status"] == "paused"
    assert state["weight"] == "0.900000"
    assert state["dest_used"] == "850"
    assert state["flags"] == "noout"


def test_ceph_restart_idempotence_avoids_second_migration(tmp_path: Path) -> None:
    first = _apply(tmp_path, "resume-migrated.cluster")
    second = _apply(tmp_path, "resume-migrated.cluster")
    assert first == second
    assert first["moves"] == "0"


def test_ceph_sweep_publishes_every_cluster_state(tmp_path: Path) -> None:
    output = tmp_path / "published"
    result = subprocess.run(
        [
            str(GOVERN),
            "sweep",
            str(POLICY),
            str(SCENARIOS / "catalog.txt"),
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    generation = (output / "current").resolve()
    assert len(list((generation / "states").glob("*.state"))) == 12
    summary = _read_fields(generation / "summary.state")
    assert summary["clusters"] == "12"
    assert summary["valid"] == "12"


def test_ceph_sweep_deterministic_replay_is_byte_stable(
    tmp_path: Path,
) -> None:
    output = tmp_path / "published"
    command = [
        str(GOVERN),
        "sweep",
        str(POLICY),
        str(SCENARIOS / "catalog.txt"),
        str(output),
    ]
    first = subprocess.run(command, check=True, capture_output=True, text=True)
    first_target = os.readlink(output / "current")
    copy = tmp_path / "first"
    shutil.copytree((output / "current").resolve(), copy)
    second = subprocess.run(command, check=True, capture_output=True, text=True)
    assert first.stdout == second.stdout
    assert first_target == os.readlink(output / "current")
    for path in copy.rglob("*"):
        if path.is_file():
            relative = path.relative_to(copy)
            assert path.read_bytes() == ((output / "current").resolve() / relative).read_bytes()


def test_ceph_rejected_and_interrupted_sweeps_preserve_current_generation(
    tmp_path: Path,
) -> None:
    output = tmp_path / "published"
    command = [
        str(GOVERN),
        "sweep",
        str(POLICY),
        str(SCENARIOS / "catalog.txt"),
        str(output),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    before = os.readlink(output / "current")

    environment = os.environ.copy()
    environment["CEPH_FAILPOINT"] = "before_publish"
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.returncode == 4
    assert os.readlink(output / "current") == before
    assert not list((output / "generations").glob(".tmp-*"))


def test_ceph_fullness_config_mutation_tightens_nearfull_gate(
    tmp_path: Path,
) -> None:
    original = _apply(tmp_path, "nearfull-headroom.cluster")
    policy = _variant_policy(
        tmp_path,
        "tight-headroom",
        {
            "fullness.conf": (
                "backfill_headroom_ratio=0.01",
                "backfill_headroom_ratio=0.03",
            )
        },
    )
    changed = _apply(tmp_path, "nearfull-headroom.cluster", policy)
    assert original["status"] == "complete"
    assert changed["status"] == "paused"
    assert changed["moves"] == "0"


def test_ceph_flag_config_mutation_blocks_unsafe_ownership(
    tmp_path: Path,
) -> None:
    policy = _variant_policy(
        tmp_path,
        "unsafe-flag-policy",
        {
            "flags.conf": (
                "clear_only_owned=true",
                "clear_only_owned=false",
            )
        },
    )
    changed = _apply(tmp_path, "safe-direct.cluster", policy)
    assert changed["status"] == "paused"
    assert "flag-policy" in changed["trace"]
    assert changed["flags"] == ""


def test_ceph_minimum_weight_config_mutation_changes_low_target(
    tmp_path: Path,
) -> None:
    cluster = _mutated_cluster(
        tmp_path,
        "stage-reweight.cluster",
        {"id": "low-target", "target_weight": "0.04"},
        "low-target.cluster",
    )
    protected = _apply_path(tmp_path, cluster)
    policy = _variant_policy(
        tmp_path,
        "zero-minimum",
        {
            "reweight.conf": (
                "minimum_weight=0.05",
                "minimum_weight=0.00",
            )
        },
    )
    permissive = _apply_path(tmp_path, cluster, policy)
    assert protected["status"] == "paused"
    assert permissive["status"] == "staged"
