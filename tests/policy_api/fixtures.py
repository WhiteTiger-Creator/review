"""Policy API fixtures with deterministic response bytes."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _bytes(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


PRODUCTION_REVISION = "prod-policy-2026-04"
STAGING_REVISION = "staging-policy-2026-03"

IDENTITY_PRODUCTION = {
    "required_roles": [
        {
            "source_id": "pol_app_owner",
            "role_id": "app_owner",
            "role_name": "app_owner",
            "login": False,
            "inherit": True,
            "createdb": False,
            "createrole": False,
            "replication": False,
            "bypassrls": False,
            "connection_limit": -1,
        },
        {
            "source_id": "pol_monitor",
            "role_id": "monitor_role",
            "role_name": "monitor_role",
            "login": False,
            "inherit": True,
            "createdb": False,
            "createrole": False,
            "replication": False,
            "bypassrls": False,
            "connection_limit": 10,
        },
    ],
    "role_constraints": [
        {
            "role_id_or_star": "*",
            "forbidden_true_attributes": [
                "createdb",
                "createrole",
                "replication",
                "bypassrls",
            ],
            "forced_boolean_attributes": {},
            "maximum_connection_limit_or_null": None,
        }
    ],
    "required_memberships": [
        {
            "membership_id": "pol_mem_monitor",
            "member_role_id": "app_login",
            "granted_role_id": "monitor_role",
        }
    ],
    "forbidden_memberships": [],
}

DATABASE_PRODUCTION = {
    "required_databases": [],
    "database_constraints": [
        {
            "database_id_or_star": "*",
            "forbidden_templates": ["template1"],
            "forced_encoding_or_null": None,
            "maximum_connection_limit_or_null": 200,
            "allowed_environments": ["development", "staging", "production"],
        }
    ],
    "required_extensions": [],
    "setting_policies": [
        {
            "setting_name": "max_connections",
            "scope_or_star": "system",
            "forced_value_or_null": 200,
            "minimum_integer_or_null": None,
            "maximum_integer_or_null": None,
            "forbidden": False,
            "required": False,
        },
        {
            "setting_name": "shared_preload_libraries",
            "scope_or_star": "system",
            "forced_value_or_null": None,
            "minimum_integer_or_null": None,
            "maximum_integer_or_null": None,
            "forbidden": False,
            "required": True,
        },
    ],
}

ACCESS_PRODUCTION = {
    "required_privileges": [
        {
            "source_id": "pol_connect",
            "grant_id": "pol_req_connect",
            "scope": "database",
            "database_id": "app_primary",
            "schema_name_or_null": None,
            "table_name_or_null": None,
            "grantee_role_id": "app_login",
            "privileges": ["CONNECT"],
            "grant_option": False,
        }
    ],
    "privilege_rules": [
        {
            "scope": "database",
            "allowed_privileges": ["CONNECT", "CREATE"],
            "forbid_grant_option": True,
            "forbid_direct_login_role_grants": True,
        },
        {
            "scope": "schema",
            "allowed_privileges": ["USAGE", "CREATE"],
            "forbid_grant_option": False,
            "forbid_direct_login_role_grants": False,
        },
    ],
    "mandatory_hba_rules": [
        {
            "hba_id": "pol_reject_broad",
            "connection_type": "host",
            "database_selector": "all",
            "role_selector": "all",
            "ipv4_cidr_or_null": "192.168.0.0/16",
            "auth_method": "reject",
            "priority": 1000,
        }
    ],
}

IDENTITY_STAGING = {
    "required_roles": [],
    "role_constraints": [
        {
            "role_id_or_star": "*",
            "forbidden_true_attributes": ["replication", "bypassrls"],
            "forced_boolean_attributes": {},
            "maximum_connection_limit_or_null": None,
        }
    ],
    "required_memberships": [],
    "forbidden_memberships": [],
}

DATABASE_STAGING = {
    "required_databases": [],
    "database_constraints": [
        {
            "database_id_or_star": "*",
            "forbidden_templates": [],
            "forced_encoding_or_null": None,
            "maximum_connection_limit_or_null": None,
            "allowed_environments": ["staging"],
        }
    ],
    "required_extensions": [],
    "setting_policies": [],
}

ACCESS_STAGING = {
    "required_privileges": [],
    "privilege_rules": [
        {
            "scope": "database",
            "allowed_privileges": ["CONNECT", "CREATE"],
            "forbid_grant_option": False,
            "forbid_direct_login_role_grants": False,
        }
    ],
    "mandatory_hba_rules": [],
}


def fragment_response(
    environment: str, revision: str, fragment_id: str, document: dict
) -> tuple[bytes, str]:
    body_obj = {
        "fragment_id": fragment_id,
        "policy_revision": revision,
        "environment": environment,
        "document": document,
    }
    body = _bytes(body_obj)
    return body, _digest(body)


def manifest_for(
    environment: str, revision: str, fragments: list[tuple[str, str]]
) -> bytes:
    obj = {
        "policy_revision": revision,
        "environment": environment,
        "fragments": [
            {"fragment_id": fid, "body_sha256": digest} for fid, digest in fragments
        ],
    }
    return _bytes(obj)


def production_fragments() -> dict[str, tuple[bytes, str]]:
    docs = {
        "identity": IDENTITY_PRODUCTION,
        "database": DATABASE_PRODUCTION,
        "access": ACCESS_PRODUCTION,
    }
    out = {}
    for fid, doc in docs.items():
        body, digest = fragment_response("production", PRODUCTION_REVISION, fid, doc)
        out[fid] = (body, digest)
    return out


def staging_fragments() -> dict[str, tuple[bytes, str]]:
    docs = {
        "identity": IDENTITY_STAGING,
        "database": DATABASE_STAGING,
        "access": ACCESS_STAGING,
    }
    out = {}
    for fid, doc in docs.items():
        body, digest = fragment_response("staging", STAGING_REVISION, fid, doc)
        out[fid] = (body, digest)
    return out


PROD_FRAGS = production_fragments()
STG_FRAGS = staging_fragments()

PROD_MANIFEST = manifest_for(
    "production",
    PRODUCTION_REVISION,
    [(fid, PROD_FRAGS[fid][1]) for fid in ["identity", "database", "access"]],
)
STG_MANIFEST = manifest_for(
    "staging",
    STAGING_REVISION,
    [(fid, STG_FRAGS[fid][1]) for fid in ["identity", "database", "access"]],
)
