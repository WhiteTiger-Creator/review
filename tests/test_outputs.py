"""Verifier tests for the PostgreSQL bootstrap policy snapshot planner.

The candidate ships a native Rust release binary (``pg-bootstrap plan ...``)
that reads local YAML/TOML/JSON inputs, fetches a per-environment policy
snapshot from a localhost HTTP API, plans each cluster, and emits
``bootstrap.sql`` plus ``bootstrap_plan.json``.

Candidate-facing tests treat the release binary as a black box executed only
through the verifier-owned isolation wrapper. Tests inspect only the named
behavior under test rather than full private golden byte equality.

The localhost policy API (``policy_api.app``) is started once per session and
its scenario/request log are reset before and after every test.
"""

from __future__ import annotations

import copy
import json
import os
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import policy_api.app as policy_app
import pytest
import toml
import yaml
from helpers.projections import sha256_bytes
from policy_api.fixtures import (
    ACCESS_PRODUCTION,
    ACCESS_STAGING,
    DATABASE_PRODUCTION,
    DATABASE_STAGING,
    IDENTITY_PRODUCTION,
    IDENTITY_STAGING,
    PRODUCTION_REVISION,
    STAGING_REVISION,
    fragment_response,
    manifest_for,
)

DATA_DIR = Path("/app/data")
SEEDS = [7, 19, 41, 83, 127]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def policy_server():
    """Start the verifier-controlled localhost policy API once for the whole session."""
    server, url = policy_app.start_server()
    try:
        yield url
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture(autouse=True)
def _reset_policy_scenario(policy_server: str):
    policy_app.reset_scenario()
    yield
    policy_app.reset_scenario()


# ---------------------------------------------------------------------------
# Binary invocation and comparison helpers
# ---------------------------------------------------------------------------


DEFAULT_BIN = "/app/target/release/pg-bootstrap"
ISOLATION_WRAPPER = os.environ.get(
    "ISOLATION_WRAPPER", "/tests/run_candidate_isolated.sh"
)


def _binary_path() -> Path:
    return Path(os.environ.get("PG_BOOTSTRAP_BIN", DEFAULT_BIN))


def _copy_fixture_data(dest: Path) -> dict[str, Path]:
    dest.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name in (
        "clusters.yaml",
        "maintenance.toml",
        "extension_catalog.json",
        "setting_catalog.json",
    ):
        target = dest / name
        shutil.copy(DATA_DIR / name, target)
        paths[name] = target
    return paths


def _write_yaml(path: Path, obj: Any) -> None:
    path.write_text(yaml.safe_dump(obj, sort_keys=False), encoding="utf-8")


def _write_toml(path: Path, obj: Any) -> None:
    path.write_text(toml.dumps(obj), encoding="utf-8")


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def _run_binary(
    yaml_path: Path,
    toml_path: Path,
    ext_path: Path,
    setting_path: Path,
    policy_url: str,
    sql_out: Path,
    plan_out: Path,
    timeout: float = 60.0,
) -> subprocess.CompletedProcess:
    binary = _binary_path()
    wrapper = Path(os.environ.get("ISOLATION_WRAPPER", ISOLATION_WRAPPER))
    args = [
        "bash",
        str(wrapper),
        str(binary),
        "--",
        "plan",
        "--yaml",
        str(yaml_path),
        "--toml",
        str(toml_path),
        "--extension-catalog",
        str(ext_path),
        "--setting-catalog",
        str(setting_path),
        "--policy-url",
        policy_url,
        "--sql-out",
        str(sql_out),
        "--plan-out",
        str(plan_out),
    ]
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    try:
        return subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, env=env
        )
    except subprocess.TimeoutExpired:
        print(f"candidate binary timed out after {timeout}s: {args}", file=sys.stderr)
        raise


def _run_scenario(
    tmp_path: Path,
    policy_url: str,
    clusters_obj: dict[str, Any],
    *,
    settings_obj: dict[str, Any] | None = None,
    ext_catalog_obj: dict[str, Any] | None = None,
    setting_catalog_obj: dict[str, Any] | None = None,
    subdir: str = "case",
) -> tuple[dict[str, Any], str, subprocess.CompletedProcess]:
    """Run one scenario through the isolated candidate. Returns plan, sql text, proc."""
    case_dir = tmp_path / subdir
    paths = _copy_fixture_data(case_dir)
    _write_yaml(paths["clusters.yaml"], clusters_obj)
    if settings_obj is not None:
        _write_toml(paths["maintenance.toml"], settings_obj)
    if ext_catalog_obj is not None:
        _write_json(paths["extension_catalog.json"], ext_catalog_obj)
    if setting_catalog_obj is not None:
        _write_json(paths["setting_catalog.json"], setting_catalog_obj)

    sql_out = case_dir / "bootstrap.sql"
    plan_out = case_dir / "bootstrap_plan.json"
    proc = _run_binary(
        paths["clusters.yaml"],
        paths["maintenance.toml"],
        paths["extension_catalog.json"],
        paths["setting_catalog.json"],
        policy_url,
        sql_out,
        plan_out,
    )
    assert proc.returncode == 0, (
        f"candidate binary failed: rc={proc.returncode} stderr={proc.stderr}"
    )
    actual_plan = json.loads(plan_out.read_text(encoding="utf-8"))
    actual_sql = sql_out.read_text(encoding="utf-8")
    return actual_plan, actual_sql, proc


def _patch_policy_fragment(
    monkeypatch: pytest.MonkeyPatch,
    environment: str,
    *,
    identity: dict[str, Any] | None = None,
    database: dict[str, Any] | None = None,
    access: dict[str, Any] | None = None,
) -> None:
    """Override the identity/database/access documents served for one environment.

    Recomputes fragment bytes, digests, and the manifest so the localhost policy
    server advertises a self-consistent, still digest-verifiable snapshot for the
    overridden documents.
    """
    if environment == "production":
        base = {
            "identity": IDENTITY_PRODUCTION,
            "database": DATABASE_PRODUCTION,
            "access": ACCESS_PRODUCTION,
        }
        revision = PRODUCTION_REVISION
        frags_attr, manifest_attr = "PROD_FRAGS", "PROD_MANIFEST"
    elif environment == "staging":
        base = {
            "identity": IDENTITY_STAGING,
            "database": DATABASE_STAGING,
            "access": ACCESS_STAGING,
        }
        revision = STAGING_REVISION
        frags_attr, manifest_attr = "STG_FRAGS", "STG_MANIFEST"
    else:
        raise ValueError(f"unsupported environment: {environment}")

    overrides = {"identity": identity, "database": database, "access": access}
    frags: dict[str, tuple[bytes, str]] = {}
    for fragment_id in ("identity", "database", "access"):
        doc = overrides[fragment_id]
        doc = (
            copy.deepcopy(doc) if doc is not None else copy.deepcopy(base[fragment_id])
        )
        frags[fragment_id] = fragment_response(environment, revision, fragment_id, doc)
    manifest = manifest_for(
        environment,
        revision,
        [(fid, frags[fid][1]) for fid in ("identity", "database", "access")],
    )
    monkeypatch.setattr(policy_app, frags_attr, frags)
    monkeypatch.setattr(policy_app, manifest_attr, manifest)


# ---------------------------------------------------------------------------
# Scenario builder helpers (mirror the local input schema in models.rs)
# ---------------------------------------------------------------------------


def _role(
    role_id: str,
    role_name: str | None = None,
    *,
    login: bool = False,
    inherit: bool = True,
    createdb: bool = False,
    createrole: bool = False,
    replication: bool = False,
    bypassrls: bool = False,
    connection_limit: int = -1,
) -> dict[str, Any]:
    return {
        "role_id": role_id,
        "role_name": role_name or role_id,
        "login": login,
        "inherit": inherit,
        "createdb": createdb,
        "createrole": createrole,
        "replication": replication,
        "bypassrls": bypassrls,
        "connection_limit": connection_limit,
    }


def _required_role_as_local(environment: str, role_id: str) -> dict[str, Any]:
    """Return a policy-required role, reshaped as a local role dict for merge tests."""
    doc = IDENTITY_PRODUCTION if environment == "production" else IDENTITY_STAGING
    required = next(r for r in doc["required_roles"] if r["role_id"] == role_id)
    return {k: v for k, v in required.items() if k != "source_id"}


def _membership(
    membership_id: str, member_role_id: str, granted_role_id: str
) -> dict[str, Any]:
    return {
        "membership_id": membership_id,
        "member_role_id": member_role_id,
        "granted_role_id": granted_role_id,
    }


def _database(
    database_id: str,
    owner_role_id: str,
    *,
    database_name: str | None = None,
    template: str = "template0",
    encoding: str = "UTF8",
    connection_limit: int = 50,
    environment_allowlist: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "database_id": database_id,
        "database_name": database_name or database_id,
        "owner_role_id": owner_role_id,
        "template": template,
        "encoding": encoding,
        "connection_limit": connection_limit,
        "environment_allowlist": list(environment_allowlist)
        if environment_allowlist
        else [],
    }


def _extension(
    extension_request_id: str, database_id: str, extension_id: str, version: str
) -> dict[str, Any]:
    return {
        "extension_request_id": extension_request_id,
        "database_id": database_id,
        "extension_id": extension_id,
        "version": version,
    }


def _privilege(
    grant_id: str,
    scope: str,
    database_id: str,
    grantee_role_id: str,
    privileges: list[str],
    *,
    schema_name_or_null: str | None = None,
    table_name_or_null: str | None = None,
    grant_option: bool = False,
) -> dict[str, Any]:
    return {
        "grant_id": grant_id,
        "scope": scope,
        "database_id": database_id,
        "schema_name_or_null": schema_name_or_null,
        "table_name_or_null": table_name_or_null,
        "grantee_role_id": grantee_role_id,
        "privileges": list(privileges),
        "grant_option": grant_option,
    }


def _hba(
    hba_id: str,
    connection_type: str,
    database_selector: str,
    role_selector: str,
    auth_method: str,
    priority: int,
    *,
    ipv4_cidr_or_null: str | None = None,
) -> dict[str, Any]:
    return {
        "hba_id": hba_id,
        "connection_type": connection_type,
        "database_selector": database_selector,
        "role_selector": role_selector,
        "ipv4_cidr_or_null": ipv4_cidr_or_null,
        "auth_method": auth_method,
        "priority": priority,
    }


def _cluster(
    cluster_id: str,
    environment: str,
    *,
    roles: list[dict[str, Any]] | None = None,
    role_memberships: list[dict[str, Any]] | None = None,
    databases: list[dict[str, Any]] | None = None,
    extensions: list[dict[str, Any]] | None = None,
    privileges: list[dict[str, Any]] | None = None,
    hba_rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "cluster_id": cluster_id,
        "environment": environment,
        "roles": roles or [],
        "role_memberships": role_memberships or [],
        "databases": databases or [],
        "extensions": extensions or [],
        "privileges": privileges or [],
        "hba_rules": hba_rules or [],
    }


def _clusters_doc(*clusters: dict[str, Any]) -> dict[str, Any]:
    return {"clusters": list(clusters)}


def _setting(
    setting_id: str,
    cluster_id: str,
    scope: str,
    setting_name: str,
    value: Any,
    *,
    database_id: str | None = None,
    role_id: str | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "setting_id": setting_id,
        "cluster_id": cluster_id,
        "scope": scope,
        "setting_name": setting_name,
        "value": value,
    }
    if database_id is not None:
        entry["database_id_or_null"] = database_id
    if role_id is not None:
        entry["role_id_or_null"] = role_id
    return entry


def _settings_doc(*settings: dict[str, Any]) -> dict[str, Any]:
    return {"settings": list(settings)}


# ---------------------------------------------------------------------------
# 01. Build
# ---------------------------------------------------------------------------

def test_01_release_binary_exists_and_produces_a_successful_baseline_plan(
    tmp_path: Path, policy_server: str
) -> None:
    """Release binary exists, isolation denies verifier trees, and baseline planning succeeds."""
    binary = _binary_path()
    assert binary.is_file(), f"expected release binary at {binary}"
    assert os.access(binary, os.X_OK), f"release binary is not executable: {binary}"
    assert str(binary) == "/app/target/release/pg-bootstrap"
    assert "debug" not in str(binary)

    wrapper = Path(os.environ.get("ISOLATION_WRAPPER", ISOLATION_WRAPPER))
    selfcheck = subprocess.run(
        ["bash", str(wrapper), str(binary), "--", "plan"],
        text=True,
        capture_output=True,
        env={
            **{k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
            "CANDIDATE_ISOLATION_SELFCHECK": "1",
        },
        check=False,
    )
    assert selfcheck.returncode == 0, selfcheck.stderr
    assert "ISOLATION_OK" in selfcheck.stdout

    case_dir = tmp_path / "baseline"
    paths = _copy_fixture_data(case_dir)
    sql_out = case_dir / "bootstrap.sql"
    plan_out = case_dir / "bootstrap_plan.json"
    proc = _run_binary(
        paths["clusters.yaml"],
        paths["maintenance.toml"],
        paths["extension_catalog.json"],
        paths["setting_catalog.json"],
        policy_server,
        sql_out,
        plan_out,
    )
    assert proc.returncode == 0, (
        f"baseline plan failed: rc={proc.returncode} stderr={proc.stderr}"
    )
    assert sql_out.is_file()
    assert plan_out.is_file()
    plan_bytes = plan_out.read_bytes()
    sql_bytes = sql_out.read_bytes()
    plan = json.loads(plan_bytes.decode("utf-8"))
    assert plan["schema_version"] == 1
    assert plan["cluster_rows"], (
        "expected at least one cluster row for the baseline fixtures"
    )
    assert plan["sql_sha256"] == sha256_bytes(sql_bytes)


# ---------------------------------------------------------------------------
# 02. Policy snapshots
# ---------------------------------------------------------------------------


def test_02_policy_snapshot_rows_record_environment_revision_and_fragment_order(
    tmp_path: Path, policy_server: str
) -> None:
    """Policy snapshots list each environment with revision and fragments in identity→database→access order."""
    case_dir = tmp_path / "snapshots"
    paths = _copy_fixture_data(case_dir)
    sql_out = case_dir / "bootstrap.sql"
    plan_out = case_dir / "bootstrap_plan.json"
    proc = _run_binary(
        paths["clusters.yaml"],
        paths["maintenance.toml"],
        paths["extension_catalog.json"],
        paths["setting_catalog.json"],
        policy_server,
        sql_out,
        plan_out,
    )
    assert proc.returncode == 0, (
        f"baseline plan failed: rc={proc.returncode} stderr={proc.stderr}"
    )
    plan = json.loads(plan_out.read_text(encoding="utf-8"))
    snaps = plan["policy_snapshot_rows"]
    assert [s["environment"] for s in snaps] == ["production", "staging"]
    by_env = {s["environment"]: s for s in snaps}
    assert by_env["production"]["policy_revision"] == PRODUCTION_REVISION
    assert by_env["staging"]["policy_revision"] == STAGING_REVISION
    for env, snap in by_env.items():
        frag_ids = [f["fragment_id"] for f in snap["fragment_rows"]]
        assert frag_ids == ["identity", "database", "access"], (
            f"{env} fragment order: expected identity→database→access actual={frag_ids}"
        )
        for frag in snap["fragment_rows"]:
            assert re.fullmatch(r"[0-9a-f]{64}", frag["body_sha256"]), (
                f"{env}/{frag['fragment_id']} body_sha256 is not a 64-hex digest"
            )
    assert plan["summary"]["policy_snapshot_count"] == len(snaps)


# ---------------------------------------------------------------------------
# 03. Schemas
# ---------------------------------------------------------------------------

def test_03_plan_json_conforms_to_the_declared_row_and_summary_schema(
    tmp_path: Path, policy_server: str
) -> None:
    """Every row family and the summary object must expose exactly the documented keys."""
    case_dir = tmp_path / "schema"
    paths = _copy_fixture_data(case_dir)
    sql_out = case_dir / "bootstrap.sql"
    plan_out = case_dir / "bootstrap_plan.json"
    proc = _run_binary(
        paths["clusters.yaml"],
        paths["maintenance.toml"],
        paths["extension_catalog.json"],
        paths["setting_catalog.json"],
        policy_server,
        sql_out,
        plan_out,
    )
    assert proc.returncode == 0, (
        f"baseline plan failed: rc={proc.returncode} stderr={proc.stderr}"
    )
    plan = json.loads(plan_out.read_text(encoding="utf-8"))

    top_level_keys = {
        "schema_version",
        "policy_snapshot_rows",
        "cluster_rows",
        "role_rows",
        "membership_rows",
        "database_rows",
        "extension_rows",
        "privilege_rows",
        "hba_rows",
        "setting_rows",
        "operation_rows",
        "phase_rows",
        "rejection_rows",
        "summary",
        "sql_sha256",
    }
    assert set(plan.keys()) == top_level_keys
    assert isinstance(plan["schema_version"], int)
    assert re.fullmatch(r"[0-9a-f]{64}", plan["sql_sha256"])

    row_shapes = {
        "cluster_rows": {
            "cluster_id",
            "environment",
            "status",
            "reason_or_null",
            "requires_reload",
            "requires_restart",
            "role_count",
            "database_count",
            "extension_count",
            "privilege_count",
            "hba_count",
            "setting_count",
            "operation_count",
            "phase_count",
        },
        "role_rows": {
            "cluster_id",
            "role_id",
            "role_name",
            "source",
            "login",
            "inherit",
            "createdb",
            "createrole",
            "replication",
            "bypassrls",
            "connection_limit",
        },
        "membership_rows": {
            "cluster_id",
            "membership_id",
            "member_role_id",
            "granted_role_id",
            "source",
        },
        "database_rows": {
            "cluster_id",
            "database_id",
            "database_name",
            "owner_role_id",
            "template",
            "encoding",
            "connection_limit",
            "source",
        },
        "extension_rows": {
            "cluster_id",
            "database_id",
            "extension_id",
            "version",
            "selection_reason",
            "dependency_depth",
            "topological_position",
        },
        "privilege_rows": {
            "cluster_id",
            "grant_id",
            "scope",
            "database_id",
            "schema_name_or_null",
            "table_name_or_null",
            "grantee_role_id",
            "privileges",
            "grant_option",
            "source",
        },
        "hba_rows": {
            "cluster_id",
            "hba_position",
            "hba_id",
            "connection_type",
            "database_selector",
            "role_selector",
            "ipv4_cidr_or_null",
            "auth_method",
            "source",
            "mandatory",
            "priority",
        },
        "setting_rows": {
            "cluster_id",
            "setting_id",
            "scope",
            "database_id_or_null",
            "role_id_or_null",
            "setting_name",
            "normalized_value",
            "activation_mode",
            "transaction_compatible",
            "source",
        },
        "operation_rows": {
            "cluster_id",
            "operation_id",
            "operation_kind",
            "resource_id",
            "database_id_or_null",
            "depends_on_operation_ids",
            "topological_position",
            "phase_index",
        },
        "phase_rows": {
            "cluster_id",
            "phase_index",
            "phase_kind",
            "database_id_or_null",
            "transactional",
            "operation_ids",
            "requires_reload",
            "requires_restart",
        },
        "rejection_rows": {
            "cluster_id",
            "stage",
            "reason",
            "resource_id_or_null",
            "details",
        },
    }
    for field, expected_keys in row_shapes.items():
        rows = plan[field]
        assert isinstance(rows, list)
        for row in rows:
            assert set(row.keys()) == expected_keys, (
                f"{field} row has unexpected keys: {sorted(row.keys())}"
            )

    summary_keys = {
        "cluster_count",
        "accepted_cluster_count",
        "rejected_cluster_count",
        "policy_snapshot_count",
        "role_count",
        "membership_count",
        "database_count",
        "extension_count",
        "privilege_count",
        "hba_count",
        "setting_count",
        "operation_count",
        "phase_count",
        "reload_required_cluster_count",
        "restart_required_cluster_count",
    }
    assert set(plan["summary"].keys()) == summary_keys
    assert plan["summary"]["cluster_count"] == len(plan["cluster_rows"])
    assert plan["summary"]["role_count"] == len(plan["role_rows"])
    assert plan["summary"]["operation_count"] == len(plan["operation_rows"])
    assert plan["summary"]["phase_count"] == len(plan["phase_rows"])

    raw = plan_out.read_bytes()
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
    text = raw.decode("utf-8")
    assert "\t" not in text
    for line in text.splitlines():
        assert not line.endswith(" "), f"trailing space in plan JSON line: {line!r}"
    assert text == json.dumps(plan, indent=2, ensure_ascii=False) + "\n"

    top_order = list(plan.keys())
    assert top_order == [
        "schema_version",
        "policy_snapshot_rows",
        "cluster_rows",
        "role_rows",
        "membership_rows",
        "database_rows",
        "extension_rows",
        "privilege_rows",
        "hba_rows",
        "setting_rows",
        "operation_rows",
        "phase_rows",
        "rejection_rows",
        "summary",
        "sql_sha256",
    ]

    phase_by_cluster: dict[str, dict[int, dict[str, Any]]] = {}
    for prow in plan["phase_rows"]:
        phase_by_cluster.setdefault(prow["cluster_id"], {})[prow["phase_index"]] = prow
    for op in plan["operation_rows"]:
        phases = phase_by_cluster.get(op["cluster_id"], {})
        assert op["phase_index"] in phases, (
            f"operation_rows[{op['operation_id']}].phase_index: "
            f"expected a real phase index, actual={op['phase_index']}"
        )
        containing = phases[op["phase_index"]]
        assert op["operation_id"] in containing["operation_ids"], (
            f"phase_rows[{op['cluster_id']}/{op['phase_index']}].operation_ids "
            f"missing {op['operation_id']}"
        )
    for prow in plan["phase_rows"]:
        for oid in prow["operation_ids"]:
            assert any(
                o["operation_id"] == oid and o["cluster_id"] == prow["cluster_id"]
                for o in plan["operation_rows"]
            ), f"phase_rows operation_ids references unknown operation {oid}"


# ---------------------------------------------------------------------------
# 04. Normalization
# ---------------------------------------------------------------------------

def test_04_setting_value_normalization_across_all_value_types(
    tmp_path: Path, policy_server: str
) -> None:
    """string_array dedup+sort, boolean coercion, integer passthrough, and string passthrough must all match."""
    catalog = {
        "settings": [
            {
                "setting_name": "shared_preload_libraries",
                "value_type": "string_array",
                "allowed_scopes": ["system"],
                "minimum_integer_or_null": None,
                "maximum_integer_or_null": None,
                "activation_mode": "restart",
                "transaction_compatible": False,
            },
            {
                "setting_name": "default_transaction_read_only",
                "value_type": "boolean",
                "allowed_scopes": ["database"],
                "minimum_integer_or_null": None,
                "maximum_integer_or_null": None,
                "activation_mode": "new_session",
                "transaction_compatible": True,
            },
            {
                "setting_name": "statement_timeout",
                "value_type": "integer",
                "allowed_scopes": ["database"],
                "minimum_integer_or_null": 0,
                "maximum_integer_or_null": 2147483647,
                "activation_mode": "immediate",
                "transaction_compatible": True,
            },
            {
                "setting_name": "custom_log_prefix",
                "value_type": "string",
                "allowed_scopes": ["database"],
                "minimum_integer_or_null": None,
                "maximum_integer_or_null": None,
                "activation_mode": "reload",
                "transaction_compatible": True,
            },
        ]
    }
    owner = _role("norm_owner")
    db = _database("norm_db", "norm_owner", environment_allowlist=["staging"])
    cluster = _cluster("normalize-01", "staging", roles=[owner], databases=[db])
    settings_doc = _settings_doc(
        _setting(
            "s_preload",
            "normalize-01",
            "system",
            "shared_preload_libraries",
            ["zzz_ext", "pg_stat_statements", "pg_stat_statements"],
        ),
        _setting(
            "s_bool",
            "normalize-01",
            "database",
            "default_transaction_read_only",
            True,
            database_id="norm_db",
        ),
        _setting(
            "s_int",
            "normalize-01",
            "database",
            "statement_timeout",
            4500,
            database_id="norm_db",
        ),
        _setting(
            "s_str",
            "normalize-01",
            "database",
            "custom_log_prefix",
            "plain value",
            database_id="norm_db",
        ),
    )
    actual_plan, actual_sql, proc = _run_scenario(
        tmp_path,
        policy_server,
        _clusters_doc(cluster),
        settings_obj=settings_doc,
        setting_catalog_obj=catalog,
        subdir="normalize",
    )
    assert proc.returncode == 0

    rows = {
        r["setting_id"]: r
        for r in actual_plan["setting_rows"]
        if r["cluster_id"] == "normalize-01"
        and r["setting_id"] in {"s_preload", "s_bool", "s_int", "s_str"}
    }
    assert rows["s_preload"]["normalized_value"] == ["pg_stat_statements", "zzz_ext"], (
        f"setting_rows[s_preload].normalized_value: expected sorted unique array, "
        f"actual={rows['s_preload']['normalized_value']!r}"
    )
    assert rows["s_bool"]["normalized_value"] is True, (
        f"setting_rows[s_bool].normalized_value: expected True actual={rows['s_bool']['normalized_value']!r}"
    )
    assert rows["s_int"]["normalized_value"] == 4500, (
        f"setting_rows[s_int].normalized_value: expected 4500 actual={rows['s_int']['normalized_value']!r}"
    )
    assert rows["s_str"]["normalized_value"] == "plain value", (
        f"setting_rows[s_str].normalized_value: expected 'plain value' "
        f"actual={rows['s_str']['normalized_value']!r}"
    )
    assert "pg_stat_statements" in actual_sql and "zzz_ext" in actual_sql
    assert "4500" in actual_sql
    assert "plain value" in actual_sql or "'plain value'" in actual_sql


# ---------------------------------------------------------------------------
# 05. Fatal local inputs
# ---------------------------------------------------------------------------

def test_05_fatal_errors_on_malformed_or_missing_local_inputs(
    tmp_path: Path, policy_server: str
) -> None:
    """Every local-input failure mode must exit non-zero, name its failure token, and leave no output files."""
    baseline_dir = tmp_path / "fatal_baseline"
    baseline_paths = _copy_fixture_data(baseline_dir)
    baseline_yaml_text = baseline_paths["clusters.yaml"].read_text(encoding="utf-8")
    baseline_toml_text = baseline_paths["maintenance.toml"].read_text(encoding="utf-8")

    cases: list[dict[str, Any]] = [
        {"name": "missing_yaml", "token": "missing_required_input", "skip_yaml": True},
        {
            "name": "malformed_yaml",
            "token": "malformed_yaml",
            "yaml_text": "clusters: [",
        },
        {
            "name": "invalid_schema_empty",
            "token": "invalid_local_schema",
            "yaml_obj": {"clusters": []},
        },
        {
            "name": "duplicate_cluster_id",
            "token": "duplicate_cluster_id",
            "yaml_obj": _clusters_doc(
                _cluster("dup-01", "staging", roles=[_role("r1")]),
                _cluster("dup-01", "staging", roles=[_role("r2")]),
            ),
        },
        {
            "name": "unknown_environment",
            "token": "unknown_local_environment",
            "yaml_obj": _clusters_doc(_cluster("qa-01", "qa", roles=[_role("r1")])),
        },
        {
            "name": "malformed_toml",
            "token": "malformed_toml",
            "toml_text": 'settings = "unterminated',
        },
        {
            "name": "malformed_extension_catalog",
            "token": "malformed_extension_catalog",
            "json_text_key": "extension_catalog.json",
            "json_text": "{",
        },
        {
            "name": "malformed_setting_catalog",
            "token": "malformed_setting_catalog",
            "json_text_key": "setting_catalog.json",
            "json_text": "{",
        },
    ]

    for case in cases:
        case_dir = tmp_path / f"fatal_{case['name']}"
        paths = _copy_fixture_data(case_dir)

        if case.get("skip_yaml"):
            paths["clusters.yaml"].unlink()
        elif "yaml_text" in case:
            paths["clusters.yaml"].write_text(case["yaml_text"], encoding="utf-8")
        elif "yaml_obj" in case:
            _write_yaml(paths["clusters.yaml"], case["yaml_obj"])
        else:
            paths["clusters.yaml"].write_text(baseline_yaml_text, encoding="utf-8")

        if "toml_text" in case:
            paths["maintenance.toml"].write_text(case["toml_text"], encoding="utf-8")
        else:
            paths["maintenance.toml"].write_text(baseline_toml_text, encoding="utf-8")

        if case.get("json_text_key"):
            (case_dir / case["json_text_key"]).write_text(
                case["json_text"], encoding="utf-8"
            )

        sql_out = case_dir / "bootstrap.sql"
        plan_out = case_dir / "bootstrap_plan.json"
        sql_out.write_text("stale sql", encoding="utf-8")
        plan_out.write_text('{"stale": true}', encoding="utf-8")

        proc = _run_binary(
            paths["clusters.yaml"],
            paths["maintenance.toml"],
            paths["extension_catalog.json"],
            paths["setting_catalog.json"],
            policy_server,
            sql_out,
            plan_out,
        )
        assert proc.returncode != 0, f"case={case['name']} unexpectedly succeeded"
        assert case["token"] in proc.stderr, (
            f"case={case['name']}: expected token {case['token']!r} in stderr {proc.stderr!r}"
        )
        assert not sql_out.exists(), (
            f"case={case['name']}: stale sql output was not cleaned up"
        )
        assert not plan_out.exists(), (
            f"case={case['name']}: stale plan output was not cleaned up"
        )


# ---------------------------------------------------------------------------
# 06. API requests
# ---------------------------------------------------------------------------

def test_06_policy_api_requests_are_well_formed_and_ordered(
    tmp_path: Path, policy_server: str
) -> None:
    """Manifest and fragment requests must be issued per-environment, in fragment order, with correct query params."""
    policy_app.reset_scenario()
    case_dir = tmp_path / "requests"
    paths = _copy_fixture_data(case_dir)
    sql_out = case_dir / "bootstrap.sql"
    plan_out = case_dir / "bootstrap_plan.json"
    proc = _run_binary(
        paths["clusters.yaml"],
        paths["maintenance.toml"],
        paths["extension_catalog.json"],
        paths["setting_catalog.json"],
        policy_server,
        sql_out,
        plan_out,
    )
    assert proc.returncode == 0, (
        f"baseline plan failed: rc={proc.returncode} stderr={proc.stderr}"
    )

    entries = list(policy_app.REQUEST_LOG.entries)
    assert len(entries) == 8, (
        f"expected 8 requests (manifest+3 fragments per environment), got {entries}"
    )
    for entry in entries:
        assert entry["method"] == "GET"

    expected_sequence = [
        ("production", "/v1/policy/manifest"),
        ("production", "/v1/policy/fragments/identity"),
        ("production", "/v1/policy/fragments/database"),
        ("production", "/v1/policy/fragments/access"),
        ("staging", "/v1/policy/manifest"),
        ("staging", "/v1/policy/fragments/identity"),
        ("staging", "/v1/policy/fragments/database"),
        ("staging", "/v1/policy/fragments/access"),
    ]
    for entry, (env, path) in zip(entries, expected_sequence, strict=False):
        assert entry["path"] == path, f"expected path {path}, got {entry['path']}"
        assert entry["query"].get("environment") == [env], (
            f"expected environment={env}, got {entry['query']}"
        )

    revisions = {"production": PRODUCTION_REVISION, "staging": STAGING_REVISION}
    for entry, (env, path) in zip(entries, expected_sequence, strict=False):
        if path == "/v1/policy/manifest":
            continue
        assert entry["query"].get("revision") == [revisions[env]], (
            f"unexpected revision in {entry}"
        )


# ---------------------------------------------------------------------------
# 07. Fragment digests
# ---------------------------------------------------------------------------

def test_07_fragment_digest_mismatch_is_fatal_and_cleans_stale_outputs(
    tmp_path: Path, policy_server: str
) -> None:
    """A tampered fragment body (digest mismatch) must be fatal, and the failure must be transient."""
    case_dir = tmp_path / "digest"
    paths = _copy_fixture_data(case_dir)
    sql_out = case_dir / "bootstrap.sql"
    plan_out = case_dir / "bootstrap_plan.json"
    sql_out.write_text("stale", encoding="utf-8")
    plan_out.write_text("{}", encoding="utf-8")

    policy_app.set_scenario("fragment_digest_mismatch")
    proc = _run_binary(
        paths["clusters.yaml"],
        paths["maintenance.toml"],
        paths["extension_catalog.json"],
        paths["setting_catalog.json"],
        policy_server,
        sql_out,
        plan_out,
    )
    assert proc.returncode != 0
    assert "fragment_digest_mismatch" in proc.stderr
    assert not sql_out.exists()
    assert not plan_out.exists()

    policy_app.reset_scenario()
    ok_dir = tmp_path / "digest_ok"
    ok_paths = _copy_fixture_data(ok_dir)
    ok_sql_out = ok_dir / "bootstrap.sql"
    ok_plan_out = ok_dir / "bootstrap_plan.json"
    ok_proc = _run_binary(
        ok_paths["clusters.yaml"],
        ok_paths["maintenance.toml"],
        ok_paths["extension_catalog.json"],
        ok_paths["setting_catalog.json"],
        policy_server,
        ok_sql_out,
        ok_plan_out,
    )
    assert ok_proc.returncode == 0, (
        "resetting the scenario should restore normal, successful planning"
    )
    assert ok_sql_out.exists()
    assert ok_plan_out.exists()


# ---------------------------------------------------------------------------
# 08. API transport failures
# ---------------------------------------------------------------------------

def test_08_policy_api_transport_and_manifest_validation_failures(
    tmp_path: Path, policy_server: str
) -> None:
    """Every remaining API failure mode must be surfaced as the correct fatal token with no partial output."""
    mode_tokens = {
        "manifest_500": "policy_api_status_error",
        "manifest_404": "policy_api_status_error",
        "manifest_bad_content_type": "policy_api_content_type_invalid",
        "manifest_malformed": "policy_manifest_invalid",
        "manifest_env_mismatch": "policy_environment_mismatch",
        "manifest_duplicate_fragment": "duplicate_policy_fragment",
        "manifest_unknown_fragment": "unknown_policy_fragment",
        "manifest_missing_fragment": "missing_policy_fragment",
        "fragment_500": "policy_api_status_error",
        "fragment_bad_content_type": "policy_api_content_type_invalid",
        "fragment_malformed": "fragment_digest_mismatch",
        "fragment_revision_mismatch": "fragment_digest_mismatch",
        "fragment_env_mismatch": "fragment_digest_mismatch",
        "fragment_id_mismatch": "fragment_digest_mismatch",
        "connection_refused": "policy_api_unavailable",
        "redirect": "policy_api_redirect_forbidden",
    }

    for mode, token in mode_tokens.items():
        case_dir = tmp_path / f"apifail_{mode}"
        paths = _copy_fixture_data(case_dir)
        sql_out = case_dir / "bootstrap.sql"
        plan_out = case_dir / "bootstrap_plan.json"

        policy_app.set_scenario(mode)
        proc = _run_binary(
            paths["clusters.yaml"],
            paths["maintenance.toml"],
            paths["extension_catalog.json"],
            paths["setting_catalog.json"],
            policy_server,
            sql_out,
            plan_out,
        )
        policy_app.reset_scenario()

        assert proc.returncode != 0, f"mode={mode} unexpectedly succeeded"
        assert token in proc.stderr, (
            f"mode={mode}: expected token {token!r} in stderr {proc.stderr!r}"
        )
        assert not sql_out.exists(), f"mode={mode}: stale sql output was not cleaned up"
        assert not plan_out.exists(), (
            f"mode={mode}: stale plan output was not cleaned up"
        )


# ---------------------------------------------------------------------------
# 09. Merge precedence
# ---------------------------------------------------------------------------

def test_09_merge_precedence_between_local_and_policy_required_resources(
    tmp_path: Path, policy_server: str
) -> None:
    """A local role matching a policy-required role merges cleanly; a mismatched one is a hard conflict."""
    app_login = _role("app_login", login=True, connection_limit=10)
    matching_owner = _required_role_as_local("production", "app_owner")
    # A production cluster needs a locally declared "app_primary" database (with
    # "app_login" present) or the policy's mandatory app_primary CONNECT grant
    # (ACCESS_PRODUCTION.required_privileges) makes it unreachable and rejects
    # the whole cluster with privilege_target_unavailable.
    merge_ok_cluster = _cluster(
        "merge-ok-01",
        "production",
        roles=[app_login, matching_owner],
        databases=[
            _database("app_primary", "app_owner", environment_allowlist=["production"])
        ],
    )

    conflicting_monitor = _required_role_as_local("production", "monitor_role")
    conflicting_monitor["connection_limit"] = 999
    merge_conflict_cluster = _cluster(
        "merge-conflict-01", "production", roles=[conflicting_monitor]
    )

    clusters_doc = _clusters_doc(merge_ok_cluster, merge_conflict_cluster)
    actual_plan, actual_sql, proc = _run_scenario(
        tmp_path,
        policy_server,
        clusters_doc,
        subdir="merge",
    )
    assert proc.returncode == 0

    rows = {r["cluster_id"]: r for r in actual_plan["cluster_rows"]}
    assert rows["merge-ok-01"]["status"] == "accepted"
    assert rows["merge-conflict-01"]["status"] == "rejected"
    assert rows["merge-conflict-01"]["reason_or_null"] == "resource_identity_conflict"

    owner_row = next(
        r
        for r in actual_plan["role_rows"]
        if r["cluster_id"] == "merge-ok-01" and r["role_id"] == "app_owner"
    )
    assert owner_row["source"] == "merged"
    monitor_row = next(
        r
        for r in actual_plan["role_rows"]
        if r["cluster_id"] == "merge-ok-01" and r["role_id"] == "monitor_role"
    )
    assert monitor_row["source"] == "policy_required"
    login_row = next(
        r
        for r in actual_plan["role_rows"]
        if r["cluster_id"] == "merge-ok-01" and r["role_id"] == "app_login"
    )
    assert login_row["source"] == "local"


# ---------------------------------------------------------------------------
# 10. Injection-resistant identifiers
# ---------------------------------------------------------------------------

def test_10_injection_resistant_identifier_rendering(
    tmp_path: Path, policy_server: str
) -> None:
    """Role/database names containing quotes and SQL keywords must be safely quoted, not executed."""
    weird_owner = _role(
        "weird_owner",
        "weird\"owner'; DROP TABLE pg_roles; --",
        login=True,
        connection_limit=5,
    )
    weird_db = _database(
        "tricky_db",
        "weird_owner",
        database_name="inj'ected\"db",
        environment_allowlist=["staging"],
    )
    cluster = _cluster(
        "injection-01", "staging", roles=[weird_owner], databases=[weird_db]
    )
    clusters_doc = _clusters_doc(cluster)
    actual_plan, actual_sql, proc = _run_scenario(
        tmp_path,
        policy_server,
        clusters_doc,
        subdir="injection",
    )
    assert proc.returncode == 0

    assert '"weird""owner\'; DROP TABLE pg_roles; --"' in actual_sql
    assert '"inj\'ected""db"' in actual_sql
    assert (
        actual_sql.count("DROP TABLE") == 2
    )  # only inside quoted identifiers, never as a bare statement
    for line in actual_sql.splitlines():
        stripped = line.strip()
        if (
            stripped.upper().startswith("DROP TABLE")
            or stripped.upper() == "DROP TABLE PG_ROLES;"
        ):
            raise AssertionError(f"DROP TABLE escaped its quoted identifier: {line!r}")


# ---------------------------------------------------------------------------
# 11. Summary counters
# ---------------------------------------------------------------------------


def test_11_summary_counters_match_row_lengths_and_status_splits(
    tmp_path: Path, policy_server: str
) -> None:
    """Summary accepted/rejected counts and family counters match the emitted row families."""
    ok = _cluster(
        "sum-ok-01",
        "staging",
        roles=[_role("sum_owner")],
        databases=[
            _database("sum_db", "sum_owner", environment_allowlist=["staging"])
        ],
        hba_rules=[_hba("sum_local", "local", "all", "all", "peer", 1)],
    )
    bad = _cluster(
        "sum-bad-01",
        "staging",
        roles=[_role("sum_bad", bypassrls=True)],
    )
    actual_plan, _sql, proc = _run_scenario(
        tmp_path,
        policy_server,
        _clusters_doc(ok, bad),
        subdir="summary",
    )
    assert proc.returncode == 0
    summary = actual_plan["summary"]
    statuses = {r["cluster_id"]: r["status"] for r in actual_plan["cluster_rows"]}
    assert statuses["sum-ok-01"] == "accepted"
    assert statuses["sum-bad-01"] == "rejected"
    assert summary["cluster_count"] == len(actual_plan["cluster_rows"]) == 2
    assert summary["accepted_cluster_count"] == 1
    assert summary["rejected_cluster_count"] == 1
    assert summary["role_count"] == len(actual_plan["role_rows"])
    assert summary["membership_count"] == len(actual_plan["membership_rows"])
    assert summary["database_count"] == len(actual_plan["database_rows"])
    assert summary["extension_count"] == len(actual_plan["extension_rows"])
    assert summary["privilege_count"] == len(actual_plan["privilege_rows"])
    assert summary["hba_count"] == len(actual_plan["hba_rows"])
    assert summary["setting_count"] == len(actual_plan["setting_rows"])
    assert summary["operation_count"] == len(actual_plan["operation_rows"])
    assert summary["phase_count"] == len(actual_plan["phase_rows"])
    assert summary["role_count"] > 0
    assert summary["database_count"] > 0
    assert summary["hba_count"] > 0
    assert all(r["cluster_id"] != "sum-bad-01" for r in actual_plan["role_rows"])
    assert len(actual_plan["rejection_rows"]) == 1
    assert actual_plan["rejection_rows"][0]["cluster_id"] == "sum-bad-01"
    assert actual_plan["rejection_rows"][0]["reason"] == "forbidden_role_capability"


# ---------------------------------------------------------------------------
# 12. Membership cycles
# ---------------------------------------------------------------------------

def test_12_membership_cycle_detection_rejects_self_loops_and_cycles(
    tmp_path: Path, policy_server: str
) -> None:
    """Self-loops and multi-node cycles in role membership graphs must be rejected; acyclic edges must pass."""
    self_loop_cluster = _cluster(
        "cycle-self-01",
        "staging",
        roles=[_role("cycle_self_role")],
        role_memberships=[_membership("m1", "cycle_self_role", "cycle_self_role")],
    )
    triangle_cluster = _cluster(
        "cycle-triangle-01",
        "staging",
        roles=[_role("role_a"), _role("role_b"), _role("role_c")],
        role_memberships=[
            _membership("m1", "role_a", "role_b"),
            _membership("m2", "role_b", "role_c"),
            _membership("m3", "role_c", "role_a"),
        ],
    )
    acyclic_cluster = _cluster(
        "cycle-none-01",
        "staging",
        roles=[_role("acyclic_a"), _role("acyclic_b")],
        role_memberships=[_membership("m1", "acyclic_a", "acyclic_b")],
    )

    clusters_doc = _clusters_doc(self_loop_cluster, triangle_cluster, acyclic_cluster)
    actual_plan, actual_sql, proc = _run_scenario(
        tmp_path,
        policy_server,
        clusters_doc,
        subdir="membershipcycle",
    )
    assert proc.returncode == 0

    reasons = {
        r["cluster_id"]: r["reason_or_null"] for r in actual_plan["cluster_rows"]
    }
    assert reasons["cycle-self-01"] == "role_membership_cycle"
    assert reasons["cycle-triangle-01"] == "role_membership_cycle"
    assert reasons["cycle-none-01"] is None

    triangle_rejection = next(
        r
        for r in actual_plan["rejection_rows"]
        if r["cluster_id"] == "cycle-triangle-01"
    )
    # Require a cycle_members detail list covering the triangle nodes without
    # pinning exact order (agents commonly emit rotated cycles).
    members = triangle_rejection["details"]["cycle_members"]
    assert isinstance(members, list)
    assert set(members) == {"role_a", "role_b", "role_c"}


# ---------------------------------------------------------------------------
# 13. Database constraints
# ---------------------------------------------------------------------------

def test_13_database_dependency_and_constraint_enforcement(
    tmp_path: Path, policy_server: str
) -> None:
    """Missing owners, forbidden templates, environment allowlists, and connection limits must all be enforced."""
    owner_role = _role("db_owner_role", connection_limit=20)

    cluster_owner_missing = _cluster(
        "db-owner-missing-01",
        "production",
        databases=[
            _database("orphan_db", "ghost_role", environment_allowlist=["production"])
        ],
    )
    cluster_forbidden_template = _cluster(
        "db-forbidden-template-01",
        "production",
        roles=[owner_role],
        databases=[
            _database(
                "forbidden_template_db",
                "db_owner_role",
                template="template1",
                environment_allowlist=["production"],
            )
        ],
    )
    cluster_env_forbidden = _cluster(
        "db-env-forbidden-01",
        "production",
        roles=[owner_role],
        databases=[
            _database(
                "env_forbidden_db", "db_owner_role", environment_allowlist=["staging"]
            )
        ],
    )
    cluster_conn_limit = _cluster(
        "db-conn-limit-01",
        "production",
        roles=[owner_role],
        databases=[
            _database(
                "over_limit_db",
                "db_owner_role",
                connection_limit=500,
                environment_allowlist=["production"],
            )
        ],
    )

    app_login = _role("app_login", login=True, connection_limit=10)
    cluster_ok = _cluster(
        "db-ok-accept-01",
        "production",
        roles=[app_login],
        databases=[
            _database(
                "ok_db",
                "app_owner",
                connection_limit=100,
                environment_allowlist=["production"],
            ),
            # required for ACCESS_PRODUCTION.required_privileges (app_login CONNECT on app_primary)
            _database("app_primary", "app_owner", environment_allowlist=["production"]),
        ],
    )

    clusters_doc = _clusters_doc(
        cluster_owner_missing,
        cluster_forbidden_template,
        cluster_env_forbidden,
        cluster_conn_limit,
        cluster_ok,
    )
    actual_plan, actual_sql, proc = _run_scenario(
        tmp_path,
        policy_server,
        clusters_doc,
        subdir="dbdeps",
    )
    assert proc.returncode == 0

    reasons = {
        r["cluster_id"]: r["reason_or_null"] for r in actual_plan["cluster_rows"]
    }
    assert reasons["db-owner-missing-01"] == "database_owner_unavailable"
    assert reasons["db-forbidden-template-01"] == "database_constraint_violation"
    assert reasons["db-env-forbidden-01"] == "database_environment_forbidden"
    assert reasons["db-conn-limit-01"] == "database_constraint_violation"
    assert reasons["db-ok-accept-01"] is None


# ---------------------------------------------------------------------------
# 14. Extension closure
# ---------------------------------------------------------------------------

def test_14_extension_dependency_closure_orders_by_depth(
    tmp_path: Path, policy_server: str
) -> None:
    """Missing dependency extensions must be auto-injected, ordered by dependency depth then extension id."""
    catalog = {
        "extensions": [
            {
                "extension_id": "cube",
                "allowed_versions": ["1.5"],
                "requires": [],
                "trusted": True,
                "required_settings": [],
            },
            {
                "extension_id": "earthdistance",
                "allowed_versions": ["1.1"],
                "requires": ["cube"],
                "trusted": True,
                "required_settings": [],
            },
            {
                "extension_id": "level_c",
                "allowed_versions": ["1.0"],
                "requires": [],
                "trusted": True,
                "required_settings": [],
            },
            {
                "extension_id": "level_b",
                "allowed_versions": ["1.0"],
                "requires": ["level_c"],
                "trusted": True,
                "required_settings": [],
            },
            {
                "extension_id": "level_a",
                "allowed_versions": ["1.0"],
                "requires": ["level_b"],
                "trusted": True,
                "required_settings": [],
            },
        ]
    }
    owner = _role("closure_owner")
    db_one = _database(
        "closure_db_one", "closure_owner", environment_allowlist=["staging"]
    )
    db_two = _database(
        "closure_db_two", "closure_owner", environment_allowlist=["staging"]
    )
    cluster = _cluster(
        "extension-closure-01",
        "staging",
        roles=[owner],
        databases=[db_one, db_two],
        extensions=[
            _extension("req_a", "closure_db_one", "level_a", "1.0"),
            _extension("req_e", "closure_db_two", "earthdistance", "1.1"),
        ],
    )
    clusters_doc = _clusters_doc(cluster)
    actual_plan, actual_sql, proc = _run_scenario(
        tmp_path,
        policy_server,
        clusters_doc,
        ext_catalog_obj=catalog,
        subdir="extclosure",
    )
    assert proc.returncode == 0

    rows = [
        r
        for r in actual_plan["extension_rows"]
        if r["cluster_id"] == "extension-closure-01"
    ]
    by_ext = {(r["database_id"], r["extension_id"]): r for r in rows}
    assert by_ext[("closure_db_one", "level_c")]["dependency_depth"] == 0, (
        f"extension_rows[(closure_db_one, level_c)].dependency_depth: expected 0 "
        f"actual={by_ext[('closure_db_one', 'level_c')]['dependency_depth']!r}"
    )
    assert by_ext[("closure_db_one", "level_b")]["dependency_depth"] == 1
    assert by_ext[("closure_db_one", "level_a")]["dependency_depth"] == 2
    assert by_ext[("closure_db_one", "level_b")]["selection_reason"] == "dependency"
    assert by_ext[("closure_db_one", "level_c")]["selection_reason"] == "dependency"
    assert by_ext[("closure_db_one", "level_a")]["selection_reason"] == "local"
    assert by_ext[("closure_db_two", "cube")]["dependency_depth"] == 0
    assert by_ext[("closure_db_two", "earthdistance")]["dependency_depth"] == 1
    assert (
        by_ext[("closure_db_one", "level_c")]["topological_position"]
        < by_ext[("closure_db_one", "level_b")]["topological_position"]
        < by_ext[("closure_db_one", "level_a")]["topological_position"]
    )
    assert (
        by_ext[("closure_db_two", "cube")]["topological_position"]
        < by_ext[("closure_db_two", "earthdistance")]["topological_position"]
    )


# ---------------------------------------------------------------------------
# 15. Extension conflicts
# ---------------------------------------------------------------------------

def test_15_extension_dependency_conflicts_are_rejected(
    tmp_path: Path, policy_server: str
) -> None:
    """Version conflicts, unknown extensions, ambiguous dependencies, and dependency cycles must all be rejected."""
    catalog = {
        "extensions": [
            {
                "extension_id": "iso_ext",
                "allowed_versions": ["1.0", "2.0"],
                "requires": [],
                "trusted": True,
                "required_settings": [],
            },
            {
                "extension_id": "ambiguous_dep",
                "allowed_versions": ["1.0", "2.0"],
                "requires": [],
                "trusted": True,
                "required_settings": [],
            },
            {
                "extension_id": "needs_ambiguous",
                "allowed_versions": ["1.0"],
                "requires": ["ambiguous_dep"],
                "trusted": True,
                "required_settings": [],
            },
            {
                "extension_id": "cyc_a",
                "allowed_versions": ["1.0"],
                "requires": ["cyc_b"],
                "trusted": True,
                "required_settings": [],
            },
            {
                "extension_id": "cyc_b",
                "allowed_versions": ["1.0"],
                "requires": ["cyc_a"],
                "trusted": True,
                "required_settings": [],
            },
        ]
    }

    version_conflict_cluster = _cluster(
        "ext-version-conflict-01",
        "staging",
        roles=[_role("ext_owner_1")],
        databases=[
            _database("ext_db_1", "ext_owner_1", environment_allowlist=["staging"])
        ],
        extensions=[
            _extension("req1", "ext_db_1", "iso_ext", "1.0"),
            _extension("req2", "ext_db_1", "iso_ext", "2.0"),
        ],
    )
    unknown_cluster = _cluster(
        "ext-unknown-01",
        "staging",
        roles=[_role("ext_owner_2")],
        databases=[
            _database("ext_db_2", "ext_owner_2", environment_allowlist=["staging"])
        ],
        extensions=[_extension("req1", "ext_db_2", "does_not_exist", "1.0")],
    )
    ambiguous_cluster = _cluster(
        "ext-ambiguous-dep-01",
        "staging",
        roles=[_role("ext_owner_3")],
        databases=[
            _database("ext_db_3", "ext_owner_3", environment_allowlist=["staging"])
        ],
        extensions=[_extension("req1", "ext_db_3", "needs_ambiguous", "1.0")],
    )
    cycle_cluster = _cluster(
        "ext-cycle-01",
        "staging",
        roles=[_role("ext_owner_4")],
        databases=[
            _database("ext_db_4", "ext_owner_4", environment_allowlist=["staging"])
        ],
        extensions=[_extension("req1", "ext_db_4", "cyc_a", "1.0")],
    )

    clusters_doc = _clusters_doc(
        version_conflict_cluster, unknown_cluster, ambiguous_cluster, cycle_cluster
    )
    actual_plan, actual_sql, proc = _run_scenario(
        tmp_path,
        policy_server,
        clusters_doc,
        ext_catalog_obj=catalog,
        subdir="extconflict",
    )
    assert proc.returncode == 0

    reasons = {
        r["cluster_id"]: r["reason_or_null"] for r in actual_plan["cluster_rows"]
    }
    assert reasons["ext-version-conflict-01"] == "extension_version_conflict"
    assert reasons["ext-unknown-01"] == "unknown_extension"
    assert reasons["ext-ambiguous-dep-01"] == "extension_dependency_missing"
    assert reasons["ext-cycle-01"] == "extension_dependency_cycle"


# ---------------------------------------------------------------------------
# 16. Staging SQL emits CREATE ROLE / CREATE DATABASE
# ---------------------------------------------------------------------------

def test_16_accepted_staging_cluster_emits_create_role_and_database_sql(
    tmp_path: Path, policy_server: str
) -> None:
    """An accepted staging cluster must render CREATE ROLE and CREATE DATABASE into bootstrap.sql."""
    owner = _role("sql_owner", login=True, connection_limit=5)
    db = _database(
        "sql_db",
        "sql_owner",
        database_name="sql_db",
        environment_allowlist=["staging"],
    )
    cluster = _cluster(
        "sql-emit-01",
        "staging",
        roles=[owner],
        databases=[db],
        hba_rules=[_hba("sql_local", "local", "all", "all", "peer", 1)],
    )
    actual_plan, actual_sql, proc = _run_scenario(
        tmp_path,
        policy_server,
        _clusters_doc(cluster),
        subdir="sqlemit",
    )
    assert proc.returncode == 0
    row = next(r for r in actual_plan["cluster_rows"] if r["cluster_id"] == "sql-emit-01")
    assert row["status"] == "accepted"
    assert "CREATE ROLE" in actual_sql.upper()
    assert "CREATE DATABASE" in actual_sql.upper()
    assert "sql_owner" in actual_sql
    assert "sql_db" in actual_sql


# ---------------------------------------------------------------------------
# 17. Duplicate local resource IDs
# ---------------------------------------------------------------------------


def test_17_duplicate_local_resource_id_is_whole_run_fatal(
    tmp_path: Path, policy_server: str
) -> None:
    """Duplicate role_id within one cluster fatals with duplicate_local_resource_id and cleans outputs."""
    case_dir = tmp_path / "dup_resource"
    paths = _copy_fixture_data(case_dir)
    clusters_doc = _clusters_doc(
        _cluster(
            "dup-role-01",
            "staging",
            roles=[_role("same_id", "first"), _role("same_id", "second")],
        )
    )
    _write_yaml(paths["clusters.yaml"], clusters_doc)
    sql_out = case_dir / "bootstrap.sql"
    plan_out = case_dir / "bootstrap_plan.json"
    sql_out.write_text("stale sql", encoding="utf-8")
    plan_out.write_text('{"stale": true}', encoding="utf-8")
    proc = _run_binary(
        paths["clusters.yaml"],
        paths["maintenance.toml"],
        paths["extension_catalog.json"],
        paths["setting_catalog.json"],
        policy_server,
        sql_out,
        plan_out,
    )
    assert proc.returncode != 0
    assert "duplicate_local_resource_id" in proc.stderr
    assert not sql_out.exists()
    assert not plan_out.exists()


# ---------------------------------------------------------------------------
# 18. Database owner availability
# ---------------------------------------------------------------------------


def test_18_database_owner_unavailable_rejects_cluster(
    tmp_path: Path, policy_server: str
) -> None:
    """A database whose owner_role_id is missing after merge rejects with database_owner_unavailable."""
    missing_owner = _cluster(
        "db-owner-missing-01",
        "staging",
        roles=[_role("present_role")],
        databases=[
            _database(
                "orphan_db",
                "ghost_owner",
                environment_allowlist=["staging"],
            )
        ],
    )
    control = _cluster(
        "db-owner-ok-01",
        "staging",
        roles=[_role("ok_owner")],
        databases=[
            _database("ok_db", "ok_owner", environment_allowlist=["staging"])
        ],
    )
    actual_plan, actual_sql, proc = _run_scenario(
        tmp_path,
        policy_server,
        _clusters_doc(missing_owner, control),
        subdir="dbowner",
    )
    assert proc.returncode == 0
    rows = {r["cluster_id"]: r for r in actual_plan["cluster_rows"]}
    assert rows["db-owner-missing-01"]["status"] == "rejected"
    assert rows["db-owner-missing-01"]["reason_or_null"] == "database_owner_unavailable"
    rejection = next(
        r
        for r in actual_plan["rejection_rows"]
        if r["cluster_id"] == "db-owner-missing-01"
    )
    assert rejection["reason"] == "database_owner_unavailable"
    assert rejection["resource_id_or_null"] == "orphan_db"
    assert rows["db-owner-ok-01"]["status"] == "accepted"
    assert "orphan_db" not in actual_sql
    assert any(r["database_id"] == "ok_db" for r in actual_plan["database_rows"])


# ---------------------------------------------------------------------------
# 19. Rejection rows for forbidden role capabilities
# ---------------------------------------------------------------------------

def test_19_forbidden_role_capability_emits_rejection_row_without_taint(
    tmp_path: Path, policy_server: str
) -> None:
    """A forbidden role capability rejects only that cluster and still emits a rejection row."""
    bad = _cluster(
        "forbid-cap-01",
        "staging",
        roles=[_role("bad_super", bypassrls=True)],
    )
    ok = _cluster(
        "forbid-cap-ok-01",
        "staging",
        roles=[_role("ok_owner")],
        databases=[
            _database("ok_db", "ok_owner", environment_allowlist=["staging"])
        ],
    )
    actual_plan, actual_sql, proc = _run_scenario(
        tmp_path,
        policy_server,
        _clusters_doc(bad, ok),
        subdir="forbidcap",
    )
    assert proc.returncode == 0
    statuses = {r["cluster_id"]: r["status"] for r in actual_plan["cluster_rows"]}
    assert statuses["forbid-cap-01"] == "rejected"
    assert statuses["forbid-cap-ok-01"] == "accepted"
    rejection = next(
        r for r in actual_plan["rejection_rows"] if r["cluster_id"] == "forbid-cap-01"
    )
    assert rejection["reason"] == "forbidden_role_capability"
    assert all(r["cluster_id"] != "forbid-cap-01" for r in actual_plan["role_rows"])
    assert "ok_owner" in actual_sql
    assert "bad_super" not in actual_sql


# ---------------------------------------------------------------------------
# 20. Setting policy
# ---------------------------------------------------------------------------

def test_20_setting_policy_forcing_and_bound_rejections(
    tmp_path: Path, policy_server: str
) -> None:
    """Policy-forced values must override local values; catalog bounds and scope references must be enforced."""
    app_login = _role("app_login", login=True, connection_limit=10)
    forced_cluster = _cluster(
        "settings-force-01",
        "production",
        roles=[app_login],
        databases=[
            _database("app_primary", "app_owner", environment_allowlist=["production"])
        ],
    )

    bounds_cluster = _cluster(
        "settings-bounds-01",
        "production",
        roles=[_role("bounds_owner")],
        databases=[
            _database("bounds_db", "bounds_owner", environment_allowlist=["production"])
        ],
    )
    scope_cluster = _cluster(
        "settings-scope-01", "production", roles=[_role("scope_owner")]
    )
    type_cluster = _cluster(
        "settings-type-01", "production", roles=[_role("type_owner")]
    )

    clusters_doc = _clusters_doc(
        forced_cluster, bounds_cluster, scope_cluster, type_cluster
    )
    settings_doc = _settings_doc(
        _setting("s_maxconn", "settings-force-01", "system", "max_connections", 999),
        _setting(
            "s_timeout",
            "settings-bounds-01",
            "database",
            "statement_timeout",
            -5,
            database_id="bounds_db",
        ),
        _setting(
            "s_idle",
            "settings-scope-01",
            "role",
            "idle_in_transaction_session_timeout",
            1000,
            role_id="ghost_role",
        ),
        _setting(
            "s_unknown", "settings-type-01", "system", "does_not_exist_setting", "x"
        ),
    )

    actual_plan, actual_sql, proc = _run_scenario(
        tmp_path,
        policy_server,
        clusters_doc,
        settings_obj=settings_doc,
        subdir="settings",
    )
    assert proc.returncode == 0

    reasons = {
        r["cluster_id"]: r["reason_or_null"] for r in actual_plan["cluster_rows"]
    }
    assert reasons["settings-force-01"] is None
    assert reasons["settings-bounds-01"] == "setting_outside_policy_bounds"
    assert reasons["settings-scope-01"] == "invalid_setting_scope"
    assert reasons["settings-type-01"] == "invalid_setting_type"

    forced_row = next(
        r
        for r in actual_plan["setting_rows"]
        if r["cluster_id"] == "settings-force-01"
        and r["setting_name"] == "max_connections"
    )
    assert forced_row["normalized_value"] == 200


# ---------------------------------------------------------------------------
# 21. Phase sequence
# ---------------------------------------------------------------------------

def test_21_phase_sequence_covers_all_boundary_kinds_in_order(
    tmp_path: Path, policy_server: str
) -> None:
    """All five phase kinds must appear, in a fixed order, both in the JSON plan and in the rendered SQL."""
    app_login = _role("app_login", login=True, connection_limit=10)
    # Named "app_primary" (rather than an arbitrary id) so this single database also
    # satisfies ACCESS_PRODUCTION's mandatory app_login CONNECT grant, keeping this
    # cluster to exactly one database and one fixed 5-phase sequence.
    db = _database("app_primary", "app_owner", environment_allowlist=["production"])
    ext = _extension("ext_req_1", "app_primary", "pg_stat_statements", "1.10")
    grant = _privilege(
        "grant_1",
        "schema",
        "app_primary",
        "app_owner",
        ["USAGE"],
        schema_name_or_null="public",
    )
    cluster = _cluster(
        "phase-full-01",
        "production",
        roles=[app_login],
        databases=[db],
        extensions=[ext],
        privileges=[grant],
    )
    clusters_doc = _clusters_doc(cluster)
    settings_doc = _settings_doc(
        _setting(
            "s_preload",
            "phase-full-01",
            "system",
            "shared_preload_libraries",
            ["pg_stat_statements"],
        )
    )
    actual_plan, actual_sql, proc = _run_scenario(
        tmp_path,
        policy_server,
        clusters_doc,
        settings_obj=settings_doc,
        subdir="phases",
    )
    assert proc.returncode == 0

    phase_rows = sorted(
        (r for r in actual_plan["phase_rows"] if r["cluster_id"] == "phase-full-01"),
        key=lambda r: r["phase_index"],
    )
    expected_kinds = [
        "cluster_transaction",
        "system_nontransactional",
        "database_create_nontransactional",
        "database_transaction",
        "configuration_reload",
    ]
    assert [r["phase_kind"] for r in phase_rows] == expected_kinds
    assert [r["phase_index"] for r in phase_rows] == list(range(len(phase_rows)))
    assert phase_rows[0]["transactional"] is True
    assert phase_rows[0]["database_id_or_null"] is None
    assert phase_rows[1]["transactional"] is False
    assert phase_rows[1]["database_id_or_null"] is None
    assert phase_rows[2]["phase_kind"] == "database_create_nontransactional"
    assert phase_rows[2]["transactional"] is False
    assert phase_rows[2]["database_id_or_null"] == "app_primary"
    assert phase_rows[3]["phase_kind"] == "database_transaction"
    assert phase_rows[3]["database_id_or_null"] == "app_primary"
    assert phase_rows[4]["requires_reload"] is True
    assert phase_rows[4]["database_id_or_null"] is None

    ops = [
        o for o in actual_plan["operation_rows"] if o["cluster_id"] == "phase-full-01"
    ]
    phase_by_idx = {p["phase_index"]: p for p in phase_rows}
    for op in ops:
        containing = phase_by_idx[op["phase_index"]]
        assert op["operation_id"] in containing["operation_ids"], (
            f"operation_rows[{op['operation_id']}].phase_index={op['phase_index']} "
            f"but phase operation_ids={containing['operation_ids']!r}"
        )
        if op["operation_kind"] == "create_database":
            assert op["database_id_or_null"] is None, (
                f"operation_rows[{op['operation_id']}].database_id_or_null: "
                f"expected null actual={op['database_id_or_null']!r}"
            )

    kind_markers = re.findall(r"-- PHASE \d+ (\S+) cluster=phase-full-01", actual_sql)
    assert kind_markers == expected_kinds
    db_tx_block = re.search(
        r"-- PHASE \d+ database_transaction cluster=phase-full-01\n(.*?)(?:\n-- PHASE|\Z)",
        actual_sql,
        flags=re.S,
    )
    assert db_tx_block is not None
    db_tx_body = db_tx_block.group(1)
    connect_idx = db_tx_body.find("\\connect")
    begin_idx = db_tx_body.find("BEGIN;")
    assert connect_idx != -1 and begin_idx != -1 and connect_idx < begin_idx
    assert "CREATE DATABASE" not in db_tx_body
    assert "ALTER SYSTEM" not in db_tx_body


# ---------------------------------------------------------------------------
# 22. Operation DAG
# ---------------------------------------------------------------------------

def test_22_operation_dag_dependencies_form_a_valid_topological_order(
    tmp_path: Path, policy_server: str
) -> None:
    """Every dependency edge must reference a real operation with a strictly smaller topological position."""
    app_login = _role("app_login", login=True, connection_limit=10)
    other_role = _role("dag_helper_role")
    membership = _membership("mem_1", "dag_helper_role", "app_owner")
    db = _database("dag_db", "app_owner", environment_allowlist=["production"])
    ext = _extension("dag_ext_req", "dag_db", "earthdistance", "1.1")
    grant = _privilege(
        "dag_grant", "database", "dag_db", "app_owner", ["CONNECT", "CREATE"]
    )
    # required for ACCESS_PRODUCTION.required_privileges (app_login CONNECT on app_primary)
    app_primary = _database(
        "app_primary", "app_owner", environment_allowlist=["production"]
    )
    cluster = _cluster(
        "dag-rich-01",
        "production",
        roles=[app_login, other_role],
        role_memberships=[membership],
        databases=[db, app_primary],
        extensions=[ext],
        privileges=[grant],
    )
    clusters_doc = _clusters_doc(cluster)
    settings_doc = _settings_doc(
        _setting(
            "dag_db_setting",
            "dag-rich-01",
            "database",
            "statement_timeout",
            5000,
            database_id="dag_db",
        ),
    )
    actual_plan, actual_sql, proc = _run_scenario(
        tmp_path,
        policy_server,
        clusters_doc,
        settings_obj=settings_doc,
        subdir="opdag",
    )
    assert proc.returncode == 0

    ops = [o for o in actual_plan["operation_rows"] if o["cluster_id"] == "dag-rich-01"]
    assert len(ops) >= 6
    by_id = {o["operation_id"]: o for o in ops}
    positions = [o["topological_position"] for o in ops]
    assert sorted(positions) == list(range(len(ops)))

    for op in ops:
        assert op["depends_on_operation_ids"] == sorted(op["depends_on_operation_ids"])
        for dep_id in op["depends_on_operation_ids"]:
            assert dep_id in by_id, (
                f"dangling dependency {dep_id} referenced by {op['operation_id']}"
            )
            assert by_id[dep_id]["topological_position"] < op["topological_position"]
        phases = [
            p for p in actual_plan["phase_rows"] if p["cluster_id"] == "dag-rich-01"
        ]
        phase_idxs = {p["phase_index"] for p in phases}
        assert op["phase_index"] in phase_idxs, (
            f"operation_rows[{op['operation_id']}].phase_index: "
            f"expected one of {sorted(phase_idxs)} actual={op['phase_index']}"
        )

    kinds_present = {o["operation_kind"] for o in ops}
    assert {
        "create_role",
        "grant_role_membership",
        "create_database",
        "connect_database",
        "create_extension",
    } <= kinds_present


# ---------------------------------------------------------------------------
# 23. SQL escaping
# ---------------------------------------------------------------------------

def test_23_sql_identifier_and_string_literal_escaping(
    tmp_path: Path, policy_server: str
) -> None:
    """Double quotes in identifiers and single quotes in string literals must be correctly doubled."""
    catalog = {
        "settings": [
            {
                "setting_name": "custom_log_prefix",
                "value_type": "string",
                "allowed_scopes": ["database"],
                "minimum_integer_or_null": None,
                "maximum_integer_or_null": None,
                "activation_mode": "reload",
                "transaction_compatible": True,
            }
        ]
    }
    owner = _role("escape_owner", 'escape"owner\\name')
    db = _database("escape_db", "escape_owner", environment_allowlist=["staging"])
    grant = _privilege(
        "grant_escape",
        "schema",
        "escape_db",
        "escape_owner",
        ["USAGE"],
        schema_name_or_null='sch"ema',
    )
    cluster = _cluster(
        "sql-escape-01", "staging", roles=[owner], databases=[db], privileges=[grant]
    )
    clusters_doc = _clusters_doc(cluster)
    settings_doc = _settings_doc(
        _setting(
            "s_log_prefix",
            "sql-escape-01",
            "database",
            "custom_log_prefix",
            "it's a 'test' value",
            database_id="escape_db",
        )
    )
    actual_plan, actual_sql, proc = _run_scenario(
        tmp_path,
        policy_server,
        clusters_doc,
        settings_obj=settings_doc,
        setting_catalog_obj=catalog,
        subdir="escaping",
    )
    assert proc.returncode == 0

    assert '"escape""owner\\name"' in actual_sql
    assert '"sch""ema"' in actual_sql
    assert "'it''s a ''test'' value'" in actual_sql


# ---------------------------------------------------------------------------
# 24. Cluster isolation
# ---------------------------------------------------------------------------

def test_24_rejected_cluster_contributes_no_rows_and_does_not_taint_accepted_cluster(
    tmp_path: Path,
    policy_server: str,
) -> None:
    """A rejected cluster must contribute zero rows and must not affect a sibling accepted cluster's output."""
    app_login = _role("app_login", login=True, connection_limit=10)
    accepted_cluster = _cluster(
        "iso-ok-01",
        "production",
        roles=[app_login],
        databases=[
            _database("iso_ok_db", "app_owner", environment_allowlist=["production"]),
            # required for ACCESS_PRODUCTION.required_privileges (app_login CONNECT on app_primary)
            _database("app_primary", "app_owner", environment_allowlist=["production"]),
        ],
    )
    rejected_cluster = _cluster(
        "iso-bad-01", "production", roles=[_role("iso_bad_role", createdb=True)]
    )

    clusters_doc = _clusters_doc(accepted_cluster, rejected_cluster)
    actual_plan, actual_sql, proc = _run_scenario(
        tmp_path,
        policy_server,
        clusters_doc,
        subdir="isolation",
    )
    assert proc.returncode == 0

    bad_row = next(
        r for r in actual_plan["cluster_rows"] if r["cluster_id"] == "iso-bad-01"
    )
    assert bad_row["status"] == "rejected"
    assert bad_row["reason_or_null"] == "forbidden_role_capability"
    for count_key in (
        "role_count",
        "database_count",
        "extension_count",
        "privilege_count",
        "hba_count",
        "setting_count",
        "operation_count",
        "phase_count",
    ):
        assert bad_row[count_key] == 0

    for row_key in (
        "role_rows",
        "membership_rows",
        "database_rows",
        "extension_rows",
        "privilege_rows",
        "hba_rows",
        "setting_rows",
        "operation_rows",
        "phase_rows",
    ):
        assert all(row["cluster_id"] != "iso-bad-01" for row in actual_plan[row_key])

    rejection_rows = [
        r for r in actual_plan["rejection_rows"] if r["cluster_id"] == "iso-bad-01"
    ]
    assert len(rejection_rows) == 1

    ok_row = next(
        r for r in actual_plan["cluster_rows"] if r["cluster_id"] == "iso-ok-01"
    )
    assert ok_row["status"] == "accepted"
    assert ok_row["role_count"] > 0
    assert any(row["cluster_id"] == "iso-ok-01" for row in actual_plan["database_rows"])
    assert "iso-bad-01" not in actual_sql
    assert "iso_bad_role" not in actual_sql


# ---------------------------------------------------------------------------
# 25. Permutation invariance
# ---------------------------------------------------------------------------

def test_25_cluster_input_order_does_not_affect_output(
    tmp_path: Path, policy_server: str
) -> None:
    """Shuffling cluster input order must not change this candidate's own baseline bytes."""
    case_dir = tmp_path / "perm_base"
    paths = _copy_fixture_data(case_dir)
    clusters_obj = yaml.safe_load(paths["clusters.yaml"].read_text(encoding="utf-8"))
    sql_out = case_dir / "bootstrap.sql"
    plan_out = case_dir / "bootstrap_plan.json"
    proc = _run_binary(
        paths["clusters.yaml"],
        paths["maintenance.toml"],
        paths["extension_catalog.json"],
        paths["setting_catalog.json"],
        policy_server,
        sql_out,
        plan_out,
    )
    assert proc.returncode == 0, (
        f"baseline plan failed: rc={proc.returncode} stderr={proc.stderr}"
    )
    baseline_plan = plan_out.read_bytes()
    baseline_sql = sql_out.read_bytes()

    for seed in SEEDS:
        shuffled = copy.deepcopy(clusters_obj)
        rng = random.Random(seed)
        rng.shuffle(shuffled["clusters"])
        seed_dir = tmp_path / f"perm_{seed}"
        seed_paths = _copy_fixture_data(seed_dir)
        _write_yaml(seed_paths["clusters.yaml"], shuffled)
        seed_sql = seed_dir / "bootstrap.sql"
        seed_plan = seed_dir / "bootstrap_plan.json"
        seed_proc = _run_binary(
            seed_paths["clusters.yaml"],
            seed_paths["maintenance.toml"],
            seed_paths["extension_catalog.json"],
            seed_paths["setting_catalog.json"],
            policy_server,
            seed_sql,
            seed_plan,
        )
        assert seed_proc.returncode == 0, f"seed={seed} failed: {seed_proc.stderr}"
        actual_plan = seed_plan.read_bytes()
        actual_sql = seed_sql.read_bytes()
        if actual_plan != baseline_plan:
            offset = next(
                (
                    i
                    for i, (a, b) in enumerate(
                        zip(baseline_plan, actual_plan, strict=False)
                    )
                    if a != b
                ),
                min(len(baseline_plan), len(actual_plan)),
            )
            raise AssertionError(
                f"seed={seed} output=bootstrap_plan.json first differing byte offset={offset}"
            )
        if actual_sql != baseline_sql:
            offset = next(
                (
                    i
                    for i, (a, b) in enumerate(
                        zip(baseline_sql, actual_sql, strict=False)
                    )
                    if a != b
                ),
                min(len(baseline_sql), len(actual_sql)),
            )
            raise AssertionError(
                f"seed={seed} output=bootstrap.sql first differing byte offset={offset}"
            )


# ---------------------------------------------------------------------------
# 26. Coupled scenario
# ---------------------------------------------------------------------------

def test_26_coupled_scenario_exercises_extensions_settings_and_forced_encoding(
    tmp_path: Path,
    policy_server: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One staging cluster combining forced encoding, extension deps, membership, and settings."""
    database_override = copy.deepcopy(DATABASE_STAGING)
    database_override["database_constraints"][0]["forced_encoding_or_null"] = "UTF8"
    _patch_policy_fragment(monkeypatch, "staging", database=database_override)

    owner = _role("coupled_owner", login=True, connection_limit=10)
    helper_role = _role("coupled_helper_role")
    membership = _membership("coupled_mem", "coupled_helper_role", "coupled_owner")

    db = _database(
        "coupled_db",
        "coupled_owner",
        encoding="LATIN1",
        connection_limit=80,
        environment_allowlist=["staging"],
    )
    ext_top = _extension("coupled_ext_top", "coupled_db", "earthdistance", "1.1")

    cluster = _cluster(
        "coupled-01",
        "staging",
        roles=[owner, helper_role],
        role_memberships=[membership],
        databases=[db],
        extensions=[ext_top],
        hba_rules=[
            _hba(
                "coupled_local_hba",
                "local",
                "coupled_db",
                "coupled_helper_role",
                "peer",
                20,
            )
        ],
    )
    clusters_doc = _clusters_doc(cluster)
    settings_doc = _settings_doc(
        _setting(
            "coupled_preload",
            "coupled-01",
            "system",
            "shared_preload_libraries",
            ["pg_stat_statements"],
        ),
        _setting(
            "coupled_timeout",
            "coupled-01",
            "database",
            "statement_timeout",
            15000,
            database_id="coupled_db",
        ),
        _setting(
            "coupled_role_idle",
            "coupled-01",
            "role",
            "idle_in_transaction_session_timeout",
            30000,
            role_id="coupled_helper_role",
        ),
    )
    actual_plan, actual_sql, proc = _run_scenario(
        tmp_path,
        policy_server,
        clusters_doc,
        settings_obj=settings_doc,
        subdir="coupled",
    )
    assert proc.returncode == 0

    row = next(
        r for r in actual_plan["cluster_rows"] if r["cluster_id"] == "coupled-01"
    )
    assert row["status"] == "accepted"

    db_row = next(
        r
        for r in actual_plan["database_rows"]
        if r["cluster_id"] == "coupled-01" and r["database_id"] == "coupled_db"
    )
    assert db_row["encoding"] == "UTF8", (
        f"database_rows[(coupled-01, coupled_db)].encoding: expected 'UTF8' actual={db_row['encoding']!r}"
    )

    ext_rows = [
        r for r in actual_plan["extension_rows"] if r["cluster_id"] == "coupled-01"
    ]
    assert {r["extension_id"] for r in ext_rows} == {"earthdistance", "cube"}
    by_ext = {r["extension_id"]: r for r in ext_rows}
    assert (
        by_ext["cube"]["topological_position"]
        < by_ext["earthdistance"]["topological_position"]
    )

    setting_ids = {
        r["setting_id"]
        for r in actual_plan["setting_rows"]
        if r["cluster_id"] == "coupled-01"
    }
    assert {"coupled_preload", "coupled_timeout", "coupled_role_idle"} <= setting_ids
    assert "CREATE ROLE" in actual_sql.upper() or "CREATE DATABASE" in actual_sql.upper()
    phases = [p for p in actual_plan["phase_rows"] if p["cluster_id"] == "coupled-01"]
    assert phases
    for p in phases:
        for oid in p["operation_ids"]:
            op = next(
                o
                for o in actual_plan["operation_rows"]
                if o["cluster_id"] == "coupled-01" and o["operation_id"] == oid
            )
            assert op["phase_index"] == p["phase_index"]


# ---------------------------------------------------------------------------
# 27. HBA reference availability
# ---------------------------------------------------------------------------


def test_27_hba_reference_unavailable_rejects_unknown_selectors(
    tmp_path: Path, policy_server: str
) -> None:
    """HBA rules that name unknown databases or roles reject with hba_reference_unavailable."""
    owner = _role("hba_ref_owner")
    db = _database("hba_ref_db", "hba_ref_owner", environment_allowlist=["staging"])
    unknown_db = _cluster(
        "hba-ref-db-01",
        "staging",
        roles=[owner],
        databases=[db],
        hba_rules=[
            _hba(
                "bad_db_sel",
                "host",
                "ghost_db",
                "hba_ref_owner",
                "scram-sha-256",
                1,
                ipv4_cidr_or_null="10.0.0.0/24",
            )
        ],
    )
    unknown_role = _cluster(
        "hba-ref-role-01",
        "staging",
        roles=[owner],
        databases=[db],
        hba_rules=[
            _hba(
                "bad_role_sel",
                "host",
                "hba_ref_db",
                "ghost_role",
                "scram-sha-256",
                1,
                ipv4_cidr_or_null="10.0.0.0/24",
            )
        ],
    )
    ok = _cluster(
        "hba-ref-ok-01",
        "staging",
        roles=[owner],
        databases=[db],
        hba_rules=[
            _hba(
                "ok_sel",
                "host",
                "hba_ref_db",
                "hba_ref_owner",
                "scram-sha-256",
                1,
                ipv4_cidr_or_null="10.0.0.0/24",
            ),
            _hba("ok_local", "local", "all", "all", "peer", 2),
        ],
    )
    actual_plan, _sql, proc = _run_scenario(
        tmp_path,
        policy_server,
        _clusters_doc(unknown_db, unknown_role, ok),
        subdir="hbaref",
    )
    assert proc.returncode == 0
    reasons = {
        r["cluster_id"]: r["reason_or_null"] for r in actual_plan["cluster_rows"]
    }
    assert reasons["hba-ref-db-01"] == "hba_reference_unavailable"
    assert reasons["hba-ref-role-01"] == "hba_reference_unavailable"
    assert reasons["hba-ref-ok-01"] is None
    for cluster_id, hba_id in (
        ("hba-ref-db-01", "bad_db_sel"),
        ("hba-ref-role-01", "bad_role_sel"),
    ):
        rejection = next(
            r for r in actual_plan["rejection_rows"] if r["cluster_id"] == cluster_id
        )
        assert rejection["reason"] == "hba_reference_unavailable"
        assert rejection["resource_id_or_null"] == hba_id
    assert any(
        r["cluster_id"] == "hba-ref-ok-01" for r in actual_plan["hba_rows"]
    )


# ---------------------------------------------------------------------------
# 28. Cluster sort order
# ---------------------------------------------------------------------------


def test_28_cluster_rows_follow_cluster_id_ascending_order(
    tmp_path: Path, policy_server: str
) -> None:
    """Cluster rows are emitted in cluster_id ascending order regardless of YAML input order."""
    clusters = [
        _cluster(
            "z-last-01",
            "staging",
            roles=[_role("z_owner")],
            databases=[
                _database("z_db", "z_owner", environment_allowlist=["staging"])
            ],
        ),
        _cluster(
            "a-first-01",
            "staging",
            roles=[_role("a_owner")],
            databases=[
                _database("a_db", "a_owner", environment_allowlist=["staging"])
            ],
        ),
        _cluster(
            "m-mid-01",
            "staging",
            roles=[_role("m_owner")],
            databases=[
                _database("m_db", "m_owner", environment_allowlist=["staging"])
            ],
        ),
    ]
    actual_plan, _sql, proc = _run_scenario(
        tmp_path,
        policy_server,
        _clusters_doc(*clusters),
        subdir="sortorder",
    )
    assert proc.returncode == 0
    emitted = [r["cluster_id"] for r in actual_plan["cluster_rows"]]
    assert emitted == sorted(emitted)
    assert emitted == ["a-first-01", "m-mid-01", "z-last-01"]
    for status in (r["status"] for r in actual_plan["cluster_rows"]):
        assert status == "accepted"


# ---------------------------------------------------------------------------
# 29. Plan JSON has trailing LF
# ---------------------------------------------------------------------------


def test_29_plan_json_ends_with_single_trailing_lf(
    tmp_path: Path, policy_server: str
) -> None:
    """bootstrap_plan.json is UTF-8 JSON ending with exactly one trailing LF."""
    cluster = _cluster(
        "lf-01",
        "staging",
        roles=[_role("lf_owner")],
        databases=[
            _database("lf_db", "lf_owner", environment_allowlist=["staging"])
        ],
    )
    case_dir = tmp_path / "trailing_lf"
    paths = _copy_fixture_data(case_dir)
    _write_yaml(paths["clusters.yaml"], _clusters_doc(cluster))
    sql_out = case_dir / "bootstrap.sql"
    plan_out = case_dir / "bootstrap_plan.json"
    proc = _run_binary(
        paths["clusters.yaml"],
        paths["maintenance.toml"],
        paths["extension_catalog.json"],
        paths["setting_catalog.json"],
        policy_server,
        sql_out,
        plan_out,
    )
    assert proc.returncode == 0
    raw = plan_out.read_bytes()
    assert raw.endswith(b"\n")
    assert not raw.endswith(b"\n\n")
    doc = json.loads(raw)
    assert "cluster_rows" in doc
    assert "summary" in doc


# ---------------------------------------------------------------------------
# 30. Membership rows appear for accepted acyclic grants
# ---------------------------------------------------------------------------


def test_30_accepted_membership_rows_are_emitted_for_acyclic_edges(
    tmp_path: Path, policy_server: str
) -> None:
    """Accepted acyclic membership edges appear in membership_rows with both endpoints."""
    cluster = _cluster(
        "mem-ok-01",
        "staging",
        roles=[_role("mem_a"), _role("mem_b")],
        role_memberships=[_membership("edge1", "mem_a", "mem_b")],
        databases=[
            _database("mem_db", "mem_a", environment_allowlist=["staging"])
        ],
    )
    actual_plan, _sql, proc = _run_scenario(
        tmp_path,
        policy_server,
        _clusters_doc(cluster),
        subdir="membrows",
    )
    assert proc.returncode == 0
    row = next(r for r in actual_plan["cluster_rows"] if r["cluster_id"] == "mem-ok-01")
    assert row["status"] == "accepted"
    mem_rows = [
        r for r in actual_plan["membership_rows"] if r["cluster_id"] == "mem-ok-01"
    ]
    assert len(mem_rows) >= 1
    assert any(
        r["member_role_id"] == "mem_a" and r["granted_role_id"] == "mem_b"
        for r in mem_rows
    )
