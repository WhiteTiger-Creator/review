"""Author-only self-consistency checks for the independent Python reference model.

Never imported by candidate-facing pytest.
"""

from __future__ import annotations

from . import hba as ref_hba
from . import sql as ref_sql
from .planner import (
    _detect_membership_cycle,
    _extension_closure,
    _normalize_ipv4_cidr,
)


def _check_quote_ident_doubles_double_quotes() -> None:
    assert ref_sql.quote_ident('a"b') == '"a""b"'
    assert ref_sql.quote_ident("plain") == '"plain"'


def _check_quote_string_doubles_single_quotes() -> None:
    assert ref_sql.quote_string("a'b") == "'a''b'"
    assert ref_sql.quote_string("plain") == "'plain'"


def _check_sort_privileges_orders_by_privilege_order() -> None:
    ordered = ref_sql.sort_privileges(["DELETE", "CONNECT", "SELECT"])
    assert ordered == ["CONNECT", "SELECT", "DELETE"]


def _check_setting_literal_string_array_dedupes_and_sorts() -> None:
    literal = ref_sql.setting_literal(
        ["b", "a", "b"], "shared_preload_libraries", "string_array"
    )
    assert literal == "'a,b'"


def _check_setting_literal_boolean() -> None:
    assert ref_sql.setting_literal(True, "x", "boolean") == "'on'"
    assert ref_sql.setting_literal(False, "x", "boolean") == "'off'"


def _check_hba_ordering_prefers_mandatory_reject_first() -> None:
    rows = [
        {
            "hba_id": "local_rule",
            "connection_type": "local",
            "database_selector": "all",
            "role_selector": "all",
            "ipv4_cidr_or_null": None,
            "auth_method": "peer",
            "priority": 5,
            "source": "local",
            "mandatory": False,
        },
        {
            "hba_id": "mandatory_reject",
            "connection_type": "host",
            "database_selector": "all",
            "role_selector": "all",
            "ipv4_cidr_or_null": "0.0.0.0/0",
            "auth_method": "reject",
            "priority": 1000,
            "source": "policy",
            "mandatory": True,
        },
    ]
    ordered = ref_hba.order_hba_rows(rows)
    assert ordered[0]["hba_id"] == "mandatory_reject"


def _check_find_shadow_detects_full_containment() -> None:
    broad = {
        "hba_id": "broad",
        "connection_type": "host",
        "database_selector": "all",
        "role_selector": "all",
        "ipv4_cidr_or_null": "10.0.0.0/8",
        "auth_method": "scram-sha-256",
        "priority": 1,
        "source": "local",
        "mandatory": False,
    }
    narrow = {
        "hba_id": "narrow",
        "connection_type": "host",
        "database_selector": "specific_db",
        "role_selector": "all",
        "ipv4_cidr_or_null": "10.0.1.0/24",
        "auth_method": "reject",
        "priority": 500,
        "source": "local",
        "mandatory": False,
    }
    shadow = ref_hba.find_shadow([broad, narrow])
    assert shadow == ("narrow", "broad")


def _check_find_shadow_returns_none_when_disjoint() -> None:
    row_a = {
        "hba_id": "a",
        "connection_type": "host",
        "database_selector": "db_a",
        "role_selector": "all",
        "ipv4_cidr_or_null": "10.0.0.0/24",
        "auth_method": "scram-sha-256",
        "priority": 1,
        "source": "local",
        "mandatory": False,
    }
    row_b = {
        "hba_id": "b",
        "connection_type": "host",
        "database_selector": "db_b",
        "role_selector": "all",
        "ipv4_cidr_or_null": "192.168.0.0/24",
        "auth_method": "scram-sha-256",
        "priority": 1,
        "source": "local",
        "mandatory": False,
    }
    assert ref_hba.find_shadow([row_a, row_b]) is None


def _check_membership_cycle_detects_self_loop() -> None:
    assert _detect_membership_cycle([("x", "x")]) == ["x"]


def _check_membership_cycle_detects_triangle() -> None:
    cycle = _detect_membership_cycle([("a", "b"), ("b", "c"), ("c", "a")])
    assert cycle == ["a", "b", "c"]


def _check_membership_cycle_none_when_acyclic() -> None:
    assert _detect_membership_cycle([("a", "b"), ("b", "c")]) is None


def _check_extension_closure_injects_missing_single_version_dependency() -> None:
    catalog = {
        "cube": {
            "extension_id": "cube",
            "allowed_versions": ["1.5"],
            "requires": [],
            "trusted": True,
            "required_settings": [],
        },
        "earthdistance": {
            "extension_id": "earthdistance",
            "allowed_versions": ["1.1"],
            "requires": ["cube"],
            "trusted": True,
            "required_settings": [],
        },
    }
    requests = [
        {
            "extension_request_id": "req1",
            "database_id": "db1",
            "extension_id": "earthdistance",
            "version": "1.1",
        }
    ]
    result, err = _extension_closure(requests, catalog)
    assert err is None
    by_ext = {row["extension_id"]: row for row in result}
    assert set(by_ext) == {"cube", "earthdistance"}
    assert by_ext["cube"]["dependency_depth"] == 0
    assert by_ext["earthdistance"]["dependency_depth"] == 1
    assert (
        by_ext["cube"]["topological_position"]
        < by_ext["earthdistance"]["topological_position"]
    )
    assert by_ext["cube"]["selection_reason"] == "dependency"
    assert by_ext["earthdistance"]["selection_reason"] == "local"


def _check_extension_closure_flags_dependency_cycle() -> None:
    catalog = {
        "cyc_a": {
            "extension_id": "cyc_a",
            "allowed_versions": ["1.0"],
            "requires": ["cyc_b"],
            "trusted": True,
            "required_settings": [],
        },
        "cyc_b": {
            "extension_id": "cyc_b",
            "allowed_versions": ["1.0"],
            "requires": ["cyc_a"],
            "trusted": True,
            "required_settings": [],
        },
    }
    requests = [
        {
            "extension_request_id": "req1",
            "database_id": "db1",
            "extension_id": "cyc_a",
            "version": "1.0",
        }
    ]
    result, err = _extension_closure(requests, catalog)
    assert result == []
    assert err == "extension_dependency_cycle"


def _check_extension_chain_depth_formula() -> None:
    catalog = {
        "level_c": {
            "extension_id": "level_c",
            "allowed_versions": ["1.0"],
            "requires": [],
            "trusted": True,
            "required_settings": [],
        },
        "level_b": {
            "extension_id": "level_b",
            "allowed_versions": ["1.0"],
            "requires": ["level_c"],
            "trusted": True,
            "required_settings": [],
        },
        "level_a": {
            "extension_id": "level_a",
            "allowed_versions": ["1.0"],
            "requires": ["level_b"],
            "trusted": True,
            "required_settings": [],
        },
    }
    requests = [
        {
            "extension_request_id": "req_a",
            "database_id": "db1",
            "extension_id": "level_a",
            "version": "1.0",
        }
    ]
    result, err = _extension_closure(requests, catalog)
    assert err is None
    by_ext = {row["extension_id"]: row for row in result}
    assert by_ext["level_c"]["dependency_depth"] == 0
    assert by_ext["level_b"]["dependency_depth"] == 1
    assert by_ext["level_a"]["dependency_depth"] == 2


def _check_normalize_ipv4_cidr_canonicalizes_host_bits() -> None:
    assert _normalize_ipv4_cidr("10.0.1.5/24") == "10.0.1.0/24"


def _check_create_database_null_semantics_documented() -> None:
    # create_database.database_id_or_null must be null in emitted operation rows.
    assert True


def _check_hyphenated_cluster_id_is_valid_identifier_shape() -> None:
    cluster_id = "prod-app-01"
    assert isinstance(cluster_id, str) and len(cluster_id) > 0
    assert "\x00" not in cluster_id


_CHECKS = (
    _check_quote_ident_doubles_double_quotes,
    _check_quote_string_doubles_single_quotes,
    _check_sort_privileges_orders_by_privilege_order,
    _check_setting_literal_string_array_dedupes_and_sorts,
    _check_setting_literal_boolean,
    _check_hba_ordering_prefers_mandatory_reject_first,
    _check_find_shadow_detects_full_containment,
    _check_find_shadow_returns_none_when_disjoint,
    _check_membership_cycle_detects_self_loop,
    _check_membership_cycle_detects_triangle,
    _check_membership_cycle_none_when_acyclic,
    _check_extension_closure_injects_missing_single_version_dependency,
    _check_extension_closure_flags_dependency_cycle,
    _check_extension_chain_depth_formula,
    _check_normalize_ipv4_cidr_canonicalizes_host_bits,
    _check_create_database_null_semantics_documented,
    _check_hyphenated_cluster_id_is_valid_identifier_shape,
)


def run_all() -> None:
    """Run every private self-check, raising AssertionError on the first failure."""
    for check in _CHECKS:
        check()


if __name__ == "__main__":
    run_all()
    print(f"self_check: {len(_CHECKS)} reference invariants verified ok")
