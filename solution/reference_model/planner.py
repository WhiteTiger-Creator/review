"""Independent PostgreSQL bootstrap policy snapshot planner reference."""

from __future__ import annotations

import hashlib
import http.client
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import toml
import yaml

from .hba import find_shadow, order_hba_rows
from .sql import (
    alter_database_setting_sql,
    alter_system_sql,
    connect_directive,
    create_database_sql,
    create_extension_sql,
    create_role_sql,
    grant_database_sql,
    grant_membership_sql,
    grant_schema_sql,
    hba_comment,
    reload_sql,
    serialize_phases,
    setting_literal,
    sort_privileges,
)

VALID_ENVIRONMENTS = {"development", "staging", "production"}
BOOL_ROLE_ATTRS = [
    "login",
    "inherit",
    "createdb",
    "createrole",
    "replication",
    "bypassrls",
]
FORBIDDEN_ATTRS = ["login", "createdb", "createrole", "replication", "bypassrls"]
SCOPE_RANK = {"database": 0, "schema": 1, "table": 2}
SETTING_SCOPE_RANK = {"system": 0, "database": 1, "role": 2, "role_database": 3}
PHASE_RANK = {
    "cluster_transaction": 0,
    "system_nontransactional": 1,
    "database_create_nontransactional": 2,
    "database_transaction": 3,
    "configuration_reload": 4,
}
OPERATION_KIND_RANK = {
    "create_role": 0,
    "grant_role_membership": 1,
    "alter_system_setting": 2,
    "create_database": 3,
    "connect_database": 4,
    "create_extension": 5,
    "grant_database_privilege": 6,
    "grant_schema_privilege": 7,
    "grant_table_privilege": 8,
    "alter_database_setting": 9,
    "alter_role_setting": 10,
    "alter_role_database_setting": 11,
    "emit_hba_rule": 12,
    "reload_configuration": 13,
}
FRAGMENT_ORDER = ["identity", "database", "access"]
CLUSTER_REJECT_ORDER = [
    "resource_identity_conflict",
    "forbidden_role_capability",
    "role_constraint_violation",
    "forbidden_membership",
    "role_membership_cycle",
    "database_owner_unavailable",
    "database_environment_forbidden",
    "database_constraint_violation",
    "unknown_extension",
    "extension_dependency_missing",
    "extension_dependency_cycle",
    "extension_version_conflict",
    "required_extension_setting_unsatisfied",
    "forbidden_privilege",
    "privilege_target_unavailable",
    "invalid_setting_scope",
    "invalid_setting_type",
    "setting_outside_policy_bounds",
    "hba_reference_unavailable",
    "hba_rule_fully_shadowed",
    "operation_dependency_cycle",
]


class PlannerError(Exception):
    def __init__(self, token: str, message: str = "") -> None:
        self.token = token
        super().__init__(f"{token}: {message}" if message else f"{token}:")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_toml(path: Path) -> Any:
    return toml.loads(path.read_text(encoding="utf-8"))


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Return the raw redirect response instead of transparently following it."""

    def http_error_302(self, req, fp, code, msg, headers):  # noqa: D401
        return fp

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


_NO_REDIRECT_OPENER = urllib.request.build_opener(_NoRedirectHandler)


def _http_get(url: str, timeout: float = 10.0) -> tuple[int, dict[str, str], bytes]:
    req = urllib.request.Request(url, method="GET")
    try:
        with _NO_REDIRECT_OPENER.open(req, timeout=timeout) as resp:
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, headers, resp.read()
    except urllib.error.HTTPError as e:
        headers = {k.lower(): v for k, v in e.headers.items()}
        return e.code, headers, e.read()
    except urllib.error.URLError as e:
        raise PlannerError("policy_api_unavailable", str(e.reason)) from e
    except http.client.HTTPException as e:
        raise PlannerError("policy_api_unavailable", str(e)) from e


def _valid_json_content_type(ct: str | None) -> bool:
    if not ct:
        return False
    base = ct.split(";")[0].strip().lower()
    return base == "application/json"


def _normalize_ipv4_cidr(cidr: str) -> str:
    import ipaddress

    net = ipaddress.IPv4Network(cidr, strict=False)
    return f"{net.network_address}/{net.prefixlen}"


def _merge_role(local: dict | None, required: dict) -> dict:
    if local is None:
        out = {k: v for k, v in required.items() if k != "source_id"}
        out["source"] = "policy_required"
        return out
    out = {**local}
    out["source"] = "merged"
    return out


def _role_key(role: dict) -> tuple:
    return tuple(role.get(a) for a in BOOL_ROLE_ATTRS) + (role.get("connection_limit"),)


def _detect_membership_cycle(edges: list[tuple[str, str]]) -> list[str] | None:
    graph: dict[str, list[str]] = {}
    nodes: set[str] = set()
    for m, g in edges:
        if m == g:
            return sorted([m])
        nodes.add(m)
        nodes.add(g)
        graph.setdefault(m, []).append(g)
    state: dict[str, int] = {n: 0 for n in nodes}
    cycle_nodes: list[str] = []

    def dfs(n: str, stack: list[str]) -> bool:
        state[n] = 1
        stack.append(n)
        for nxt in graph.get(n, []):
            if state[nxt] == 1:
                idx = stack.index(nxt)
                cycle_nodes.extend(sorted(stack[idx:]))
                return True
            if state[nxt] == 0 and dfs(nxt, stack):
                return True
        stack.pop()
        state[n] = 2
        return False

    for n in sorted(nodes):
        if state[n] == 0 and dfs(n, []):
            return sorted(set(cycle_nodes))
    return None


def _extension_closure(
    requests: list[dict], catalog: dict[str, dict]
) -> tuple[list[dict], str | None]:
    by_key: dict[tuple[str, str], dict] = {}
    for r in requests:
        key = (r["database_id"], r["extension_id"])
        if key in by_key and by_key[key]["version"] != r["version"]:
            return [], "extension_version_conflict"
        by_key[key] = dict(r)

    changed = True
    while changed:
        changed = False
        for (db_id, ext_id), _rec in list(by_key.items()):
            if ext_id not in catalog:
                return [], "unknown_extension"
            for dep in catalog[ext_id]["requires"]:
                dkey = (db_id, dep)
                if dkey not in by_key:
                    versions = catalog[dep]["allowed_versions"]
                    if len(versions) != 1:
                        return [], "extension_dependency_missing"
                    by_key[dkey] = {
                        "extension_request_id": f"dep_{db_id}_{dep}",
                        "database_id": db_id,
                        "extension_id": dep,
                        "version": versions[0],
                        "selection_reason": "dependency",
                    }
                    changed = True

    # cycle check via topo
    ext_graph: dict[str, list[str]] = {}
    for _, ext_id in by_key:
        ext_graph.setdefault(ext_id, [])
        for dep in catalog[ext_id]["requires"]:
            ext_graph.setdefault(dep, []).append(ext_id)
    indeg = {n: 0 for n in ext_graph}
    for deps in ext_graph.values():
        for d in deps:
            indeg[d] = indeg.get(d, 0) + 1
    # rebuild properly
    ext_graph = {e: list(catalog[e]["requires"]) for (_, e) in by_key}
    nodes = set(ext_graph) | {d for ds in ext_graph.values() for d in ds}
    indeg = {n: 0 for n in nodes}
    for e, deps in ext_graph.items():
        for _d in deps:
            indeg[e] = indeg.get(e, 0)
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    indeg = {n: 0 for n in nodes}
    for e, deps in ext_graph.items():
        for d in deps:
            adj.setdefault(d, []).append(e)
            indeg[e] = indeg.get(e, 0) + 1
    ready = sorted([n for n in nodes if indeg[n] == 0])
    ordered_exts: list[str] = []
    while ready:
        n = ready.pop(0)
        ordered_exts.append(n)
        for m in sorted(adj.get(n, [])):
            indeg[m] -= 1
            if indeg[m] == 0:
                ready.append(m)
                ready.sort()
    if len(ordered_exts) != len(nodes):
        return [], "extension_dependency_cycle"

    result: list[dict] = []
    pos = 0
    for db_id in sorted({k[0] for k in by_key}):
        db_exts = [(k, by_key[k]) for k in by_key if k[0] == db_id]
        db_exts.sort(
            key=lambda x: (
                ordered_exts.index(x[1]["extension_id"]),
                x[1]["extension_id"],
                x[1]["version"],
                x[1].get("extension_request_id", ""),
            )
        )
        depth_map: dict[str, int] = {}

        def depth(ext_id: str, _depth_map: dict[str, int] = depth_map) -> int:
            if ext_id in _depth_map:
                return _depth_map[ext_id]
            deps = catalog[ext_id]["requires"]
            d = 0 if not deps else 1 + max(depth(dep) for dep in deps)
            _depth_map[ext_id] = d
            return d

        for _, rec in sorted(
            db_exts,
            key=lambda x: (
                depth(x[1]["extension_id"]),
                x[1]["extension_id"],
                x[1]["version"],
                x[1].get("extension_request_id", ""),
            ),
        ):
            out = dict(rec)
            out["dependency_depth"] = depth(rec["extension_id"])
            out["topological_position"] = pos
            out.setdefault("selection_reason", "local")
            pos += 1
            result.append(out)
    return result, None


def plan_cluster(
    cluster: dict,
    settings_local: list[dict],
    ext_catalog: dict[str, dict],
    setting_catalog: dict[str, dict],
    identity_doc: dict,
    database_doc: dict,
    access_doc: dict,
) -> tuple[dict | None, dict | None]:
    """Return (accepted_plan_dict, rejection_row) for one cluster."""
    cid = cluster["cluster_id"]
    env = cluster["environment"]

    # --- roles merge ---
    roles_by_id: dict[str, dict] = {}
    for r in cluster.get("roles", []):
        roles_by_id[r["role_id"]] = {**r, "source": "local"}
    for req in identity_doc.get("required_roles", []):
        rid = req["role_id"]
        if rid in roles_by_id:
            local = roles_by_id[rid]
            if _role_key(local) != _role_key(req):
                return None, _rejection(
                    cid, "merge", "resource_identity_conflict", rid, {}
                )
            roles_by_id[rid] = _merge_role(local, req)
        else:
            roles_by_id[rid] = _merge_role(None, req)

    # role constraints
    constraints = identity_doc.get("role_constraints", [])
    for role_id, role in roles_by_id.items():
        applicable = [c for c in constraints if c["role_id_or_star"] in ("*", role_id)]
        applicable.sort(key=lambda c: 0 if c["role_id_or_star"] == role_id else 1)
        for c in applicable:
            for attr in c.get("forbidden_true_attributes", []):
                if role.get(attr):
                    return None, _rejection(
                        cid,
                        "roles",
                        "forbidden_role_capability",
                        role_id,
                        {"attribute": attr},
                    )
            for attr, val in c.get("forced_boolean_attributes", {}).items():
                if attr in role and role[attr] != val:
                    if attr in c.get("forbidden_true_attributes", []) and val:
                        return None, _rejection(
                            cid,
                            "roles",
                            "forbidden_role_capability",
                            role_id,
                            {"attribute": attr},
                        )
                    role[attr] = val
            max_lim = c.get("maximum_connection_limit_or_null")
            if (
                max_lim is not None
                and role["connection_limit"] != -1
                and role["connection_limit"] > max_lim
            ):
                return None, _rejection(
                    cid,
                    "roles",
                    "role_constraint_violation",
                    role_id,
                    {"limit": max_lim},
                )

    # memberships
    memberships: list[dict] = []
    seen_edges: set[tuple[str, str]] = set()
    for m in cluster.get("role_memberships", []):
        memberships.append({**m, "source": "local"})
        seen_edges.add((m["member_role_id"], m["granted_role_id"]))
    for req in identity_doc.get("required_memberships", []):
        edge = (req["member_role_id"], req["granted_role_id"])
        if edge not in seen_edges:
            memberships.append({**req, "source": "policy_required"})
            seen_edges.add(edge)
    for forb in identity_doc.get("forbidden_memberships", []):
        if (forb["member_role_id"], forb["granted_role_id"]) in seen_edges:
            return None, _rejection(
                cid, "roles", "forbidden_membership", forb["member_role_id"], forb
            )

    cycle = _detect_membership_cycle(
        [(m["member_role_id"], m["granted_role_id"]) for m in memberships]
    )
    if cycle:
        return None, _rejection(
            cid, "roles", "role_membership_cycle", cycle[0], {"cycle_members": cycle}
        )

    # databases
    dbs_by_id: dict[str, dict] = {}
    for d in cluster.get("databases", []):
        dbs_by_id[d["database_id"]] = {**d, "source": "local"}
    for req in database_doc.get("required_databases", []):
        did = req["database_id"]
        if did in dbs_by_id:
            local = dbs_by_id[did]
            if any(
                local.get(k) != req.get(k)
                for k in ["database_name", "owner_role_id", "template", "encoding"]
            ):
                return None, _rejection(
                    cid, "merge", "resource_identity_conflict", did, {}
                )
            dbs_by_id[did]["source"] = "merged"
        else:
            dbs_by_id[did] = {
                **{k: v for k, v in req.items() if k != "source_id"},
                "source": "policy_required",
            }

    for db_id, db in dbs_by_id.items():
        if db["owner_role_id"] not in roles_by_id:
            return None, _rejection(
                cid, "databases", "database_owner_unavailable", db_id, {}
            )
        applicable = [
            c
            for c in database_doc.get("database_constraints", [])
            if c["database_id_or_star"] in ("*", db_id)
        ]
        applicable.sort(key=lambda c: 0 if c["database_id_or_star"] == db_id else 1)
        for c in applicable:
            if env not in c.get("allowed_environments", [env]):
                return None, _rejection(
                    cid, "databases", "database_environment_forbidden", db_id, {}
                )
            if db["template"] in c.get("forbidden_templates", []):
                return None, _rejection(
                    cid,
                    "databases",
                    "database_constraint_violation",
                    db_id,
                    {"template": db["template"]},
                )
            forced_enc = c.get("forced_encoding_or_null")
            if forced_enc and db["encoding"] != forced_enc:
                db["encoding"] = forced_enc
            max_lim = c.get("maximum_connection_limit_or_null")
            if (
                max_lim is not None
                and db["connection_limit"] != -1
                and db["connection_limit"] > max_lim
            ):
                return None, _rejection(
                    cid,
                    "databases",
                    "database_constraint_violation",
                    db_id,
                    {"limit": max_lim},
                )
        if env not in db["environment_allowlist"]:
            return None, _rejection(
                cid, "databases", "database_environment_forbidden", db_id, {}
            )

    # extensions
    ext_requests: list[dict] = []
    for e in cluster.get("extensions", []):
        ext_requests.append({**e, "selection_reason": "local"})
    for req in database_doc.get("required_extensions", []):
        ext_requests.append({**req, "selection_reason": "policy_required"})
    extensions, ext_err = _extension_closure(ext_requests, ext_catalog)
    if ext_err:
        stage = "extensions"
        return None, _rejection(cid, stage, ext_err, None, {})

    # settings
    settings: list[dict] = [s for s in settings_local if s["cluster_id"] == cid]
    for sp in database_doc.get("setting_policies", []):
        if sp.get("forbidden"):
            continue
        if sp.get("required") and sp.get("forced_value_or_null") is not None:
            pass  # inject below

    effective_settings: list[dict] = []
    setting_keys: set[tuple] = set()
    for s in settings:
        effective_settings.append({**s, "source": "local"})
        setting_keys.add(
            (
                s["scope"],
                s.get("database_id_or_null"),
                s.get("role_id_or_null"),
                s["setting_name"],
            )
        )

    for sp in database_doc.get("setting_policies", []):
        if not sp.get("required"):
            continue
        if sp.get("forbidden"):
            continue
        # inject system required shared_preload for pg_stat_statements handled by local fixture
        if (
            sp["scope_or_star"] == "system"
            and sp.get("forced_value_or_null") is not None
        ):
            key = ("system", None, None, sp["setting_name"])
            if key not in setting_keys:
                effective_settings.append(
                    {
                        "setting_id": f"policy_{sp['setting_name']}",
                        "cluster_id": cid,
                        "scope": "system",
                        "database_id_or_null": None,
                        "role_id_or_null": None,
                        "setting_name": sp["setting_name"],
                        "value": sp["forced_value_or_null"],
                        "source": "policy_required",
                    }
                )

    requires_restart = False
    requires_reload = False
    resolved_settings: list[dict] = []
    for s in effective_settings:
        cat = setting_catalog.get(s["setting_name"])
        if not cat:
            return None, _rejection(
                cid, "settings", "invalid_setting_type", s["setting_id"], {}
            )
        scope = s["scope"]
        if scope not in cat["allowed_scopes"]:
            return None, _rejection(
                cid, "settings", "invalid_setting_scope", s["setting_id"], {}
            )
        if scope == "database" and s["database_id_or_null"] not in dbs_by_id:
            return None, _rejection(
                cid, "settings", "invalid_setting_scope", s["setting_id"], {}
            )
        if (
            scope in ("role", "role_database")
            and s["role_id_or_null"] not in roles_by_id
        ):
            return None, _rejection(
                cid, "settings", "invalid_setting_scope", s["setting_id"], {}
            )
        if scope == "role_database" and s["database_id_or_null"] not in dbs_by_id:
            return None, _rejection(
                cid, "settings", "invalid_setting_scope", s["setting_id"], {}
            )

        value = s["value"]
        for sp in database_doc.get("setting_policies", []):
            if (
                sp.get("forbidden")
                and (sp["scope_or_star"] == "*" or sp["scope_or_star"] == scope)
                and sp["setting_name"] == s["setting_name"]
            ):
                return None, _rejection(
                    cid,
                    "settings",
                    "setting_outside_policy_bounds",
                    s["setting_id"],
                    {},
                )
            if (sp["scope_or_star"] == "*" or sp["scope_or_star"] == scope) and sp[
                "setting_name"
            ] == s["setting_name"]:
                if sp.get("forced_value_or_null") is not None:
                    value = sp["forced_value_or_null"]
                mn = sp.get("minimum_integer_or_null")
                mx = sp.get("maximum_integer_or_null")
                if cat["value_type"] == "integer":
                    iv = int(value)
                    if mn is not None and iv < mn:
                        return None, _rejection(
                            cid,
                            "settings",
                            "setting_outside_policy_bounds",
                            s["setting_id"],
                            {},
                        )
                    if mx is not None and iv > mx:
                        return None, _rejection(
                            cid,
                            "settings",
                            "setting_outside_policy_bounds",
                            s["setting_id"],
                            {},
                        )

        vtype = cat["value_type"]
        if vtype == "integer":
            norm: Any = int(value)
            mn = cat.get("minimum_integer_or_null")
            mx = cat.get("maximum_integer_or_null")
            if mn is not None and norm < mn:
                return None, _rejection(
                    cid,
                    "settings",
                    "setting_outside_policy_bounds",
                    s["setting_id"],
                    {},
                )
            if mx is not None and norm > mx:
                return None, _rejection(
                    cid,
                    "settings",
                    "setting_outside_policy_bounds",
                    s["setting_id"],
                    {},
                )
        elif vtype == "boolean":
            norm = bool(value)
        elif vtype == "string":
            norm = str(value)
        elif vtype == "string_array":
            norm = sorted(set(str(x) for x in value), key=lambda x: x.encode("utf-8"))
        else:
            return None, _rejection(
                cid, "settings", "invalid_setting_type", s["setting_id"], {}
            )

        if cat["activation_mode"] == "restart":
            requires_restart = True
        if cat["activation_mode"] == "reload":
            requires_reload = True

        resolved_settings.append(
            {
                **s,
                "normalized_value": norm,
                "activation_mode": cat["activation_mode"],
                "transaction_compatible": cat["transaction_compatible"],
                "value_type": vtype,
            }
        )

    # extension setting coupling
    settings_by_scope: dict[tuple, dict] = {}
    for s in resolved_settings:
        settings_by_scope[
            (
                s["scope"],
                s.get("database_id_or_null"),
                s.get("role_id_or_null"),
                s["setting_name"],
            )
        ] = s
    for ext in extensions:
        cat_e = ext_catalog[ext["extension_id"]]
        for req in cat_e.get("required_settings", []):
            key = (req["scope"], None, None, req["setting_name"])
            eff = settings_by_scope.get(key)
            if not eff:
                return None, _rejection(
                    cid,
                    "extensions",
                    "required_extension_setting_unsatisfied",
                    ext["extension_id"],
                    {},
                )
            if req.get("required_value_contains_or_null"):
                needle = req["required_value_contains_or_null"]
                if needle not in eff["normalized_value"]:
                    return None, _rejection(
                        cid,
                        "extensions",
                        "required_extension_setting_unsatisfied",
                        ext["extension_id"],
                        {},
                    )
            if req.get("required_value_equals_or_null") is not None:
                if eff["normalized_value"] != req["required_value_equals_or_null"]:
                    return None, _rejection(
                        cid,
                        "extensions",
                        "required_extension_setting_unsatisfied",
                        ext["extension_id"],
                        {},
                    )

    # privileges
    privs: list[dict] = []
    priv_index: dict[tuple, dict] = {}
    for p in cluster.get("privileges", []):
        privs.append({**p, "source": "local"})
    for req in access_doc.get("required_privileges", []):
        privs.append({**req, "source": "policy_required"})

    merged_privs: list[dict] = []
    for p in privs:
        sem = (
            p["scope"],
            p["database_id"],
            p.get("schema_name_or_null"),
            p.get("table_name_or_null"),
            p["grantee_role_id"],
            p["grant_option"],
        )
        if sem in priv_index:
            existing = priv_index[sem]
            combined = sort_privileges(
                list(set(existing["privileges"]) | set(p["privileges"]))
            )
            existing["privileges"] = combined
            if existing["source"] != p["source"]:
                existing["source"] = "merged"
        else:
            entry = {**p, "privileges": sort_privileges(list(p["privileges"]))}
            priv_index[sem] = entry
            merged_privs.append(entry)

    privilege_rules = access_doc.get("privilege_rules", [])
    for p in merged_privs:
        if p["database_id"] not in dbs_by_id:
            return None, _rejection(
                cid, "privileges", "privilege_target_unavailable", p["grant_id"], {}
            )
        if p["grantee_role_id"] not in roles_by_id:
            return None, _rejection(
                cid, "privileges", "privilege_target_unavailable", p["grant_id"], {}
            )
        for rule in privilege_rules:
            if rule["scope"] != p["scope"]:
                continue
            for priv in p["privileges"]:
                if priv not in rule.get("allowed_privileges", []):
                    return None, _rejection(
                        cid,
                        "privileges",
                        "forbidden_privilege",
                        p["grant_id"],
                        {"privilege": priv},
                    )
            if p["grant_option"] and rule.get("forbid_grant_option"):
                return None, _rejection(
                    cid, "privileges", "forbidden_privilege", p["grant_id"], {}
                )
            grantee = roles_by_id[p["grantee_role_id"]]
            if (
                grantee["login"]
                and rule.get("forbid_direct_login_role_grants")
                and p.get("source") == "local"
            ):
                return None, _rejection(
                    cid, "privileges", "forbidden_privilege", p["grant_id"], {}
                )

    # HBA
    hba_rows: list[dict] = []
    for h in cluster.get("hba_rules", []):
        row = {**h, "source": "local", "mandatory": False}
        if row.get("ipv4_cidr_or_null"):
            row["ipv4_cidr_or_null"] = _normalize_ipv4_cidr(row["ipv4_cidr_or_null"])
        hba_rows.append(row)
    for h in access_doc.get("mandatory_hba_rules", []):
        row = {**h, "source": "policy", "mandatory": True}
        if row.get("ipv4_cidr_or_null"):
            row["ipv4_cidr_or_null"] = _normalize_ipv4_cidr(row["ipv4_cidr_or_null"])
        hba_rows.append(row)

    for h in hba_rows:
        if h["database_selector"] != "all" and h["database_selector"] not in dbs_by_id:
            return None, _rejection(
                cid, "hba", "hba_reference_unavailable", h["hba_id"], {}
            )
        if h["role_selector"] != "all" and h["role_selector"] not in roles_by_id:
            return None, _rejection(
                cid, "hba", "hba_reference_unavailable", h["hba_id"], {}
            )

    shadow = find_shadow(hba_rows)
    if shadow:
        return None, _rejection(
            cid,
            "hba",
            "hba_rule_fully_shadowed",
            shadow[0],
            {"shadowed_hba_id": shadow[0], "shadowing_hba_id": shadow[1]},
        )

    ordered_hba = order_hba_rows(hba_rows)
    for i, h in enumerate(ordered_hba):
        h["hba_position"] = i

    # build operations (abbreviated - full DAG)
    ops: list[dict] = []
    op_deps: dict[str, list[str]] = {}

    def add_op(
        kind: str,
        resource_id: str,
        db_id: str | None = None,
        deps: list[str] | None = None,
    ) -> str:
        oid = _op_id(kind, cid, resource_id, db_id)
        ops.append(
            {
                "cluster_id": cid,
                "operation_id": oid,
                "operation_kind": kind,
                "resource_id": resource_id,
                "database_id_or_null": db_id,
                "depends_on_operation_ids": sorted(
                    deps or [], key=lambda x: x.encode("utf-8")
                ),
            }
        )
        op_deps[oid] = deps or []
        return oid

    role_ops = {}
    for rid, _role in sorted(roles_by_id.items()):
        role_ops[rid] = add_op("create_role", rid)

    for m in memberships:
        deps = [role_ops[m["member_role_id"]], role_ops[m["granted_role_id"]]]
        add_op("grant_role_membership", m["membership_id"], deps=deps)

    sys_settings = [s for s in resolved_settings if s["scope"] == "system"]
    reload_ops: list[str] = []
    for s in sys_settings:
        oid = add_op("alter_system_setting", s["setting_id"])
        if s["activation_mode"] == "reload":
            reload_ops.append(oid)

    db_ops = {}
    connect_ops = {}
    for did, db in sorted(dbs_by_id.items()):
        db_ops[did] = add_op(
            "create_database", did, deps=[role_ops[db["owner_role_id"]]]
        )
        connect_ops[did] = add_op(
            "connect_database", did, db_id=did, deps=[db_ops[did]]
        )

    ext_ops = {}
    for ext in extensions:
        eid = ext["extension_id"]
        oid = add_op(
            "extension",
            f"{ext['database_id']}:{eid}",
            db_id=ext["database_id"],
            deps=[connect_ops[ext["database_id"]]],
        )
        ext_ops[(ext["database_id"], eid)] = oid
        for dep in ext_catalog[eid]["requires"]:
            dep_oid = ext_ops.get((ext["database_id"], dep))
            if dep_oid:
                op_deps[oid].append(dep_oid)
                ops[[o["operation_id"] for o in ops].index(oid)][
                    "depends_on_operation_ids"
                ] = sorted(set(op_deps[oid]))

    for p in merged_privs:
        deps = [role_ops[p["grantee_role_id"]], connect_ops[p["database_id"]]]
        kind = {
            "database": "grant_database_privilege",
            "schema": "grant_schema_privilege",
            "table": "grant_table_privilege",
        }[p["scope"]]
        add_op(kind, p["grant_id"], db_id=p["database_id"], deps=deps)

    for s in resolved_settings:
        if s["scope"] == "system":
            continue
        deps: list[str] = []
        if s["scope"] in ("database", "role_database"):
            deps.append(connect_ops[s["database_id_or_null"]])
        if s["scope"] in ("role", "role_database"):
            deps.append(role_ops[s["role_id_or_null"]])
        kind = {
            "database": "alter_database_setting",
            "role": "alter_role_setting",
            "role_database": "alter_role_database_setting",
        }[s["scope"]]
        oid = add_op(
            kind, s["setting_id"], db_id=s.get("database_id_or_null"), deps=deps
        )
        if s["activation_mode"] == "reload":
            reload_ops.append(oid)

    hba_op_ids = []
    for h in ordered_hba:
        deps = []
        if h["database_selector"] != "all":
            deps.append(connect_ops[h["database_selector"]])
        if h["role_selector"] != "all":
            deps.append(role_ops[h["role_selector"]])
        hba_op_ids.append(add_op("emit_hba_rule", h["hba_id"], deps=deps))

    if reload_ops or hba_op_ids:
        reload_deps = reload_ops + hba_op_ids
        add_op("reload_configuration", cid, deps=reload_deps)
        requires_reload = True

    # topo sort
    topo, cycle_ops = _topo_sort(ops)
    if cycle_ops:
        return None, _rejection(
            cid,
            "graph",
            "operation_dependency_cycle",
            cycle_ops[0],
            {"operations": cycle_ops},
        )

    for i, oid in enumerate(topo):
        for o in ops:
            if o["operation_id"] == oid:
                o["topological_position"] = i

    # phases + SQL built in sql module via caller
    return {
        "cluster_id": cid,
        "environment": env,
        "roles": list(roles_by_id.values()),
        "memberships": memberships,
        "databases": list(dbs_by_id.values()),
        "extensions": extensions,
        "privileges": merged_privs,
        "hba_rows": ordered_hba,
        "settings": resolved_settings,
        "operations": ops,
        "requires_reload": requires_reload,
        "requires_restart": requires_restart,
        "topo": topo,
    }, None


def _op_id(
    kind: str, cluster_id: str, resource_id: str, db_id: str | None = None
) -> str:
    mapping = {
        "create_role": f"role:{cluster_id}:{resource_id}",
        "grant_role_membership": f"membership:{cluster_id}:{resource_id}",
        "alter_system_setting": f"system-setting:{cluster_id}:{resource_id}",
        "create_database": f"database:{cluster_id}:{resource_id}",
        "connect_database": f"connect:{cluster_id}:{resource_id}",
        "extension": f"extension:{cluster_id}:{resource_id}",
        "grant_database_privilege": f"privilege:{cluster_id}:{resource_id}",
        "grant_schema_privilege": f"privilege:{cluster_id}:{resource_id}",
        "grant_table_privilege": f"privilege:{cluster_id}:{resource_id}",
        "alter_database_setting": f"database-setting:{cluster_id}:{resource_id}",
        "alter_role_setting": f"role-setting:{cluster_id}:{resource_id}",
        "alter_role_database_setting": f"role-database-setting:{cluster_id}:{resource_id}",
        "emit_hba_rule": f"hba:{cluster_id}:{resource_id}",
        "reload_configuration": f"reload:{cluster_id}",
    }
    if kind == "extension" and db_id:
        return f"extension:{cluster_id}:{db_id}:{resource_id.split(':')[-1] if ':' in resource_id else resource_id}"
    return mapping.get(kind, f"{kind}:{cluster_id}:{resource_id}")


def _topo_sort(ops: list[dict]) -> tuple[list[str], list[str] | None]:
    ids = [o["operation_id"] for o in ops]
    indeg = {i: 0 for i in ids}
    adj: dict[str, list[str]] = {i: [] for i in ids}
    for o in ops:
        for d in o["depends_on_operation_ids"]:
            adj[d].append(o["operation_id"])
            indeg[o["operation_id"]] += 1

    def ready_key(oid: str) -> tuple:
        o = next(x for x in ops if x["operation_id"] == oid)
        kind = o["operation_kind"]
        if kind == "extension":
            kind = "create_extension"
        return (
            PHASE_RANK.get(_phase_for_kind(kind), 9),
            o["cluster_id"],
            o.get("database_id_or_null") or "",
            OPERATION_KIND_RANK.get(kind, 99),
            o["resource_id"],
            oid,
        )

    ready = sorted([i for i in ids if indeg[i] == 0], key=ready_key)
    result: list[str] = []
    while ready:
        n = ready.pop(0)
        result.append(n)
        for m in adj[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                ready.append(m)
                ready.sort(key=ready_key)
    if len(result) != len(ids):
        remaining = sorted([i for i in ids if i not in result])
        return [], remaining
    return result, None


def _phase_for_kind(kind: str) -> str:
    if kind in ("create_role", "grant_role_membership"):
        return "cluster_transaction"
    if kind == "alter_system_setting":
        return "system_nontransactional"
    if kind == "create_database":
        return "database_create_nontransactional"
    if kind in ("emit_hba_rule", "reload_configuration"):
        return "configuration_reload"
    return "database_transaction"


def _rejection(
    cluster_id: str, stage: str, reason: str, resource_id: str | None, details: dict
) -> dict:
    return {
        "cluster_id": cluster_id,
        "stage": stage,
        "reason": reason,
        "resource_id_or_null": resource_id,
        "details": details,
    }


def fetch_policy_snapshot(base_url: str, environment: str) -> dict:
    manifest_url = f"{base_url.rstrip('/')}/v1/policy/manifest?environment={urllib.parse.quote(environment)}"
    status, headers, body = _http_get(manifest_url)
    if status in (301, 302, 303, 307, 308):
        raise PlannerError("policy_api_redirect_forbidden")
    if status != 200:
        raise PlannerError("policy_api_status_error", f"status={status}")
    ct = headers.get("content-type")
    if not _valid_json_content_type(ct):
        raise PlannerError("policy_api_content_type_invalid")
    try:
        manifest = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise PlannerError("policy_manifest_invalid") from e

    for key in ["policy_revision", "environment", "fragments"]:
        if key not in manifest:
            raise PlannerError("policy_manifest_invalid")
    if manifest["environment"] != environment:
        raise PlannerError("policy_environment_mismatch")
    frags = manifest["fragments"]
    if not isinstance(frags, list):
        raise PlannerError("policy_manifest_invalid")
    frag_ids = [f.get("fragment_id") for f in frags]
    if len(frag_ids) != len(set(frag_ids)):
        raise PlannerError("duplicate_policy_fragment")
    if set(frag_ids) != set(FRAGMENT_ORDER):
        if len(frag_ids) != 3:
            raise PlannerError("missing_policy_fragment")
        unknown = set(frag_ids) - set(FRAGMENT_ORDER)
        if unknown:
            raise PlannerError("unknown_policy_fragment")
        raise PlannerError("missing_policy_fragment")

    revision = manifest["policy_revision"]
    documents: dict[str, dict] = {}
    fragment_rows = []
    for fid in FRAGMENT_ORDER:
        entry = next((f for f in frags if f["fragment_id"] == fid), None)
        if not entry:
            raise PlannerError("missing_policy_fragment")
        digest = entry.get("body_sha256", "")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise PlannerError("invalid_fragment_digest")
        fragment_rows.append({"fragment_id": fid, "body_sha256": digest})
        url = (
            f"{base_url.rstrip('/')}/v1/policy/fragments/{fid}"
            f"?environment={urllib.parse.quote(environment)}&revision={urllib.parse.quote(revision)}"
        )
        fstatus, fheaders, fbody = _http_get(url)
        if fstatus != 200:
            raise PlannerError("policy_api_status_error")
        if not _valid_json_content_type(fheaders.get("content-type")):
            raise PlannerError("policy_api_content_type_invalid")
        actual = _sha256_bytes(fbody)
        if actual != digest:
            raise PlannerError("fragment_digest_mismatch")
        try:
            frag = json.loads(fbody.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise PlannerError("malformed_policy_fragment") from e
        if frag.get("fragment_id") != fid:
            raise PlannerError("fragment_id_mismatch")
        if frag.get("policy_revision") != revision:
            raise PlannerError("policy_revision_mismatch")
        if frag.get("environment") != environment:
            raise PlannerError("policy_environment_mismatch")
        documents[fid] = frag["document"]

    return {
        "environment": environment,
        "policy_revision": revision,
        "fragment_rows": fragment_rows,
        "identity": documents["identity"],
        "database": documents["database"],
        "access": documents["access"],
    }


def run_planner(
    yaml_path: Path,
    toml_path: Path,
    ext_catalog_path: Path,
    setting_catalog_path: Path,
    policy_url: str,
    sql_out: Path,
    plan_out: Path,
) -> int:
    try:
        return _run_planner_inner(
            yaml_path,
            toml_path,
            ext_catalog_path,
            setting_catalog_path,
            policy_url,
            sql_out,
            plan_out,
        )
    except PlannerError as e:
        _cleanup_outputs(sql_out, plan_out)
        import sys

        print(f"{e.token}: {e}", file=sys.stderr)
        return 1


def _cleanup_outputs(sql_out: Path, plan_out: Path) -> None:
    for p in [
        sql_out,
        plan_out,
        sql_out.with_suffix(sql_out.suffix + ".tmp"),
        plan_out.with_suffix(plan_out.suffix + ".tmp"),
    ]:
        if p.exists():
            p.unlink()


def _run_planner_inner(
    yaml_path: Path,
    toml_path: Path,
    ext_catalog_path: Path,
    setting_catalog_path: Path,
    policy_url: Path | str,
    sql_out: Path,
    plan_out: Path,
) -> int:
    policy_url = str(policy_url)
    for path, token in [
        (yaml_path, "missing_required_input"),
        (toml_path, "missing_required_input"),
        (ext_catalog_path, "missing_required_input"),
        (setting_catalog_path, "missing_required_input"),
    ]:
        if not path.is_file():
            raise PlannerError(token, str(path))

    try:
        clusters_doc = _load_yaml(yaml_path)
    except Exception as e:
        raise PlannerError("malformed_yaml") from e
    try:
        settings_doc = _load_toml(toml_path)
    except Exception as e:
        raise PlannerError("malformed_toml") from e
    try:
        ext_cat_doc = _load_json(ext_catalog_path)
    except Exception as e:
        raise PlannerError("malformed_extension_catalog") from e
    try:
        set_cat_doc = _load_json(setting_catalog_path)
    except Exception as e:
        raise PlannerError("malformed_setting_catalog") from e

    if not isinstance(clusters_doc, dict) or "clusters" not in clusters_doc:
        raise PlannerError("invalid_local_schema")
    clusters = clusters_doc["clusters"]
    if not isinstance(clusters, list) or not clusters:
        raise PlannerError("invalid_local_schema")

    cluster_ids = [c.get("cluster_id") for c in clusters]
    if len(cluster_ids) != len(set(cluster_ids)):
        raise PlannerError("duplicate_cluster_id")

    settings_list = settings_doc.get("settings", [])
    ext_catalog = {e["extension_id"]: e for e in ext_cat_doc.get("extensions", [])}
    setting_catalog = {s["setting_name"]: s for s in set_cat_doc.get("settings", [])}

    environments = sorted(
        {c["environment"] for c in clusters}, key=lambda x: x.encode("utf-8")
    )
    for env in environments:
        if env not in VALID_ENVIRONMENTS:
            raise PlannerError("unknown_local_environment", env)

    snapshots = {env: fetch_policy_snapshot(policy_url, env) for env in environments}

    accepted_clusters: list[dict] = []
    rejections: list[dict] = []
    cluster_rows: list[dict] = []

    for cluster in sorted(clusters, key=lambda c: c["cluster_id"].encode("utf-8")):
        snap = snapshots[cluster["environment"]]
        result, rejection = plan_cluster(
            cluster,
            settings_list,
            ext_catalog,
            setting_catalog,
            snap["identity"],
            snap["database"],
            snap["access"],
        )
        if rejection:
            rejections.append(rejection)
            cluster_rows.append(
                {
                    "cluster_id": cluster["cluster_id"],
                    "environment": cluster["environment"],
                    "status": "rejected",
                    "reason_or_null": rejection["reason"],
                    "requires_reload": False,
                    "requires_restart": False,
                    "role_count": 0,
                    "database_count": 0,
                    "extension_count": 0,
                    "privilege_count": 0,
                    "hba_count": 0,
                    "setting_count": 0,
                    "operation_count": 0,
                    "phase_count": 0,
                }
            )
        else:
            accepted_clusters.append(result)
            cluster_rows.append(
                {
                    "cluster_id": cluster["cluster_id"],
                    "environment": cluster["environment"],
                    "status": "accepted",
                    "reason_or_null": None,
                    "requires_reload": result["requires_reload"],
                    "requires_restart": result["requires_restart"],
                    "role_count": len(result["roles"]),
                    "database_count": len(result["databases"]),
                    "extension_count": len(result["extensions"]),
                    "privilege_count": len(result["privileges"]),
                    "hba_count": len(result["hba_rows"]),
                    "setting_count": len(result["settings"]),
                    "operation_count": len(result["operations"]),
                    "phase_count": 0,
                }
            )

    # Build SQL and plan rows from accepted clusters
    sql_parts: list[str] = []
    all_role_rows: list[dict] = []
    all_membership_rows: list[dict] = []
    all_database_rows: list[dict] = []
    all_extension_rows: list[dict] = []
    all_privilege_rows: list[dict] = []
    all_hba_rows: list[dict] = []
    all_setting_rows: list[dict] = []
    all_operation_rows: list[dict] = []
    all_phase_rows: list[dict] = []

    roles_by_cluster: dict[str, dict[str, dict]] = {}
    dbs_by_cluster: dict[str, dict[str, dict]] = {}

    for ac in accepted_clusters:
        cid = ac["cluster_id"]
        roles_by_cluster[cid] = {r["role_id"]: r for r in ac["roles"]}
        dbs_by_cluster[cid] = {d["database_id"]: d for d in ac["databases"]}
        for r in ac["roles"]:
            all_role_rows.append(
                {
                    "cluster_id": cid,
                    **{
                        k: r[k]
                        for k in [
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
                        ]
                    },
                }
            )
        for m in ac["memberships"]:
            all_membership_rows.append(
                {
                    "cluster_id": cid,
                    **{
                        k: m[k]
                        for k in [
                            "membership_id",
                            "member_role_id",
                            "granted_role_id",
                            "source",
                        ]
                    },
                }
            )
        for d in ac["databases"]:
            all_database_rows.append(
                {
                    "cluster_id": cid,
                    **{
                        k: d[k]
                        for k in [
                            "database_id",
                            "database_name",
                            "owner_role_id",
                            "template",
                            "encoding",
                            "connection_limit",
                            "source",
                        ]
                    },
                }
            )
        for e in ac["extensions"]:
            all_extension_rows.append(
                {
                    "cluster_id": cid,
                    "database_id": e["database_id"],
                    "extension_id": e["extension_id"],
                    "version": e["version"],
                    "selection_reason": e.get("selection_reason", "local"),
                    "dependency_depth": e["dependency_depth"],
                    "topological_position": e["topological_position"],
                }
            )
        for p in ac["privileges"]:
            all_privilege_rows.append(
                {
                    "cluster_id": cid,
                    **{
                        k: p[k]
                        for k in [
                            "grant_id",
                            "scope",
                            "database_id",
                            "schema_name_or_null",
                            "table_name_or_null",
                            "grantee_role_id",
                            "privileges",
                            "grant_option",
                            "source",
                        ]
                    },
                }
            )
        for h in ac["hba_rows"]:
            all_hba_rows.append(
                {
                    "cluster_id": cid,
                    **{
                        k: h[k]
                        for k in [
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
                        ]
                    },
                }
            )
        for s in ac["settings"]:
            all_setting_rows.append(
                {
                    "cluster_id": cid,
                    "setting_id": s["setting_id"],
                    "scope": s["scope"],
                    "database_id_or_null": s.get("database_id_or_null"),
                    "role_id_or_null": s.get("role_id_or_null"),
                    "setting_name": s["setting_name"],
                    "normalized_value": s["normalized_value"],
                    "activation_mode": s["activation_mode"],
                    "transaction_compatible": s["transaction_compatible"],
                    "source": s.get("source", "local"),
                }
            )

        phases, phase_count = _build_phases_and_sql(
            ac, roles_by_cluster[cid], dbs_by_cluster[cid], setting_catalog
        )
        ac["phase_count"] = phase_count
        for cr in cluster_rows:
            if cr["cluster_id"] == cid:
                cr["phase_count"] = phase_count
        if sql_parts and phases:
            sql_parts.append("")
        sql_parts.append(phases)
        phases_struct = _build_phase_struct(
            ac, roles_by_cluster[cid], dbs_by_cluster[cid], setting_catalog
        )
        all_phase_rows.extend(_phase_rows_for_cluster(cid, phases_struct))

        op_phase = {}
        for p in phases_struct:
            for oid in p.get("operation_ids", []):
                op_phase[oid] = p["phase_index"]

        for o in ac["operations"]:
            all_operation_rows.append(
                {
                    "cluster_id": cid,
                    "operation_id": o["operation_id"],
                    "operation_kind": "create_extension"
                    if o["operation_kind"] == "extension"
                    else o["operation_kind"],
                    "resource_id": o["resource_id"],
                    "database_id_or_null": o.get("database_id_or_null"),
                    "depends_on_operation_ids": o["depends_on_operation_ids"],
                    "topological_position": o.get("topological_position", 0),
                    "phase_index": op_phase.get(o["operation_id"], 0),
                }
            )

    sql_text = "\n".join(p for p in sql_parts if p)
    if sql_text and not sql_text.endswith("\n"):
        sql_text += "\n"
    if not sql_text:
        sql_text = ""

    sql_digest = _sha256_bytes(sql_text.encode("utf-8"))

    plan = {
        "schema_version": 1,
        "policy_snapshot_rows": [
            {
                "environment": env,
                "policy_revision": snapshots[env]["policy_revision"],
                "fragment_rows": snapshots[env]["fragment_rows"],
            }
            for env in sorted(snapshots, key=lambda x: x.encode("utf-8"))
        ],
        "cluster_rows": sorted(
            cluster_rows, key=lambda r: r["cluster_id"].encode("utf-8")
        ),
        "role_rows": sorted(
            all_role_rows, key=lambda r: (r["cluster_id"], r["role_id"])
        ),
        "membership_rows": sorted(
            all_membership_rows,
            key=lambda r: (
                r["cluster_id"],
                r["member_role_id"],
                r["granted_role_id"],
                r["membership_id"],
            ),
        ),
        "database_rows": sorted(
            all_database_rows, key=lambda r: (r["cluster_id"], r["database_id"])
        ),
        "extension_rows": sorted(
            all_extension_rows,
            key=lambda r: (
                r["cluster_id"],
                r["database_id"],
                r["topological_position"],
                r["extension_id"],
            ),
        ),
        "privilege_rows": sorted(
            all_privilege_rows,
            key=lambda r: (
                r["cluster_id"],
                r["database_id"],
                SCOPE_RANK[r["scope"]],
                r.get("schema_name_or_null") or "",
                r.get("table_name_or_null") or "",
                r["grantee_role_id"],
                r["grant_id"],
            ),
        ),
        "hba_rows": sorted(
            all_hba_rows, key=lambda r: (r["cluster_id"], r["hba_position"])
        ),
        "setting_rows": sorted(
            all_setting_rows,
            key=lambda r: (
                r["cluster_id"],
                SETTING_SCOPE_RANK[r["scope"]],
                r.get("database_id_or_null") or "",
                r.get("role_id_or_null") or "",
                r["setting_name"],
                r["setting_id"],
            ),
        ),
        "operation_rows": sorted(
            all_operation_rows,
            key=lambda r: (
                r["cluster_id"],
                r["topological_position"],
                r["operation_id"],
            ),
        ),
        "phase_rows": sorted(
            all_phase_rows, key=lambda r: (r["cluster_id"], r["phase_index"])
        ),
        "rejection_rows": sorted(
            rejections, key=lambda r: r["cluster_id"].encode("utf-8")
        ),
        "summary": _summary(
            cluster_rows,
            all_role_rows,
            all_membership_rows,
            all_database_rows,
            all_extension_rows,
            all_privilege_rows,
            all_hba_rows,
            all_setting_rows,
            all_operation_rows,
            all_phase_rows,
            snapshots,
        ),
        "sql_sha256": sql_digest,
    }

    try:
        sql_out.parent.mkdir(parents=True, exist_ok=True)
        sql_tmp = sql_out.with_suffix(sql_out.suffix + ".tmp")
        plan_tmp = plan_out.with_suffix(plan_out.suffix + ".tmp")
        sql_tmp.write_text(sql_text, encoding="utf-8")
        plan_json = json.dumps(plan, indent=2, ensure_ascii=False) + "\n"
        plan_tmp.write_text(plan_json, encoding="utf-8")
        sql_tmp.replace(sql_out)
        plan_tmp.replace(plan_out)
    except OSError as e:
        raise PlannerError("output_write_failed") from e

    return 0 if rejections or accepted_clusters else 1


def _summary(
    cluster_rows,
    roles,
    memberships,
    databases,
    extensions,
    privileges,
    hbas,
    settings,
    operations,
    phases,
    snapshots,
) -> dict:
    accepted = sum(1 for c in cluster_rows if c["status"] == "accepted")
    rejected = sum(1 for c in cluster_rows if c["status"] == "rejected")
    return {
        "cluster_count": len(cluster_rows),
        "accepted_cluster_count": accepted,
        "rejected_cluster_count": rejected,
        "policy_snapshot_count": len(snapshots),
        "role_count": len(roles),
        "membership_count": len(memberships),
        "database_count": len(databases),
        "extension_count": len(extensions),
        "privilege_count": len(privileges),
        "hba_count": len(hbas),
        "setting_count": len(settings),
        "operation_count": len(operations),
        "phase_count": len(phases),
        "reload_required_cluster_count": sum(
            1 for c in cluster_rows if c.get("requires_reload")
        ),
        "restart_required_cluster_count": sum(
            1 for c in cluster_rows if c.get("requires_restart")
        ),
    }


def _build_phases_and_sql(ac, roles, dbs, setting_catalog) -> tuple[str, int]:
    struct = _build_phase_struct(ac, roles, dbs, setting_catalog)
    return serialize_phases(struct, ac["cluster_id"]), len(struct)


def _build_phase_struct(ac, roles, dbs, setting_catalog) -> list[dict]:
    phases: list[dict] = []
    idx = 0

    cluster_stmts = []
    cluster_ops = []
    for oid in ac["topo"]:
        op = next(o for o in ac["operations"] if o["operation_id"] == oid)
        if op["operation_kind"] in ("create_role",):
            role = roles[op["resource_id"]]
            cluster_stmts.append(create_role_sql(role))
            cluster_ops.append(oid)
        elif op["operation_kind"] == "grant_role_membership":
            m = next(
                m for m in ac["memberships"] if m["membership_id"] == op["resource_id"]
            )
            cluster_stmts.append(
                grant_membership_sql(
                    roles[m["granted_role_id"]]["role_name"],
                    roles[m["member_role_id"]]["role_name"],
                )
            )
            cluster_ops.append(oid)
    if cluster_stmts:
        phases.append(
            {
                "phase_index": idx,
                "phase_kind": "cluster_transaction",
                "database_id_or_null": None,
                "transactional": True,
                "statements": cluster_stmts,
                "operation_ids": cluster_ops,
                "requires_reload": False,
                "requires_restart": False,
            }
        )
        idx += 1

    for oid in ac["topo"]:
        op = next(o for o in ac["operations"] if o["operation_id"] == oid)
        if op["operation_kind"] == "alter_system_setting":
            s = next(x for x in ac["settings"] if x["setting_id"] == op["resource_id"])
            lit = setting_literal(
                s["normalized_value"], s["setting_name"], s["value_type"]
            )
            phases.append(
                {
                    "phase_index": idx,
                    "phase_kind": "system_nontransactional",
                    "database_id_or_null": None,
                    "transactional": False,
                    "statements": [alter_system_sql(s["setting_name"], lit)],
                    "operation_ids": [oid],
                    "requires_reload": s["activation_mode"] == "reload",
                    "requires_restart": s["activation_mode"] == "restart",
                }
            )
            idx += 1

    for oid in ac["topo"]:
        op = next(o for o in ac["operations"] if o["operation_id"] == oid)
        if op["operation_kind"] == "create_database":
            db = dbs[op["resource_id"]]
            owner = roles[db["owner_role_id"]]["role_name"]
            phases.append(
                {
                    "phase_index": idx,
                    "phase_kind": "database_create_nontransactional",
                    "database_id_or_null": db["database_id"],
                    "transactional": False,
                    "statements": [create_database_sql(db, owner)],
                    "operation_ids": [oid],
                    "requires_reload": False,
                    "requires_restart": False,
                }
            )
            idx += 1

    for db_id, db in sorted(dbs.items()):
        db_stmts = []
        db_ops = []
        connect_line = connect_directive(db["database_name"])
        for oid in ac["topo"]:
            op = next(o for o in ac["operations"] if o["operation_id"] == oid)
            matches_db = op.get("database_id_or_null") == db_id
            if (
                op["operation_kind"] == "connect_database"
                and op["resource_id"] == db_id
            ):
                db_ops.append(oid)
                continue
            if op["operation_kind"] == "alter_role_setting":
                continue
            if op["operation_kind"] == "alter_role_database_setting":
                if matches_db:
                    db_ops.append(oid)
                continue
            if op["operation_kind"] == "grant_table_privilege":
                if matches_db:
                    db_ops.append(oid)
                continue
            if op["operation_kind"] in ("extension", "create_extension"):
                parts = op["operation_id"].split(":")
                ext_db = parts[2] if len(parts) >= 4 else ""
                if ext_db != db_id and not matches_db:
                    continue
                ext_id = op["operation_id"].split(":")[-1]
                ext = next(
                    e
                    for e in ac["extensions"]
                    if e["extension_id"] == ext_id and e["database_id"] == db_id
                )
                db_stmts.append(create_extension_sql(ext_id, ext["version"]))
                db_ops.append(oid)
                continue
            if not matches_db:
                continue
            if op["operation_kind"] == "grant_database_privilege":
                p = next(
                    p for p in ac["privileges"] if p["grant_id"] == op["resource_id"]
                )
                db_stmts.append(
                    grant_database_sql(
                        p["privileges"],
                        db["database_name"],
                        roles[p["grantee_role_id"]]["role_name"],
                        p["grant_option"],
                    )
                )
                db_ops.append(oid)
            elif op["operation_kind"] == "grant_schema_privilege":
                p = next(
                    p for p in ac["privileges"] if p["grant_id"] == op["resource_id"]
                )
                db_stmts.append(
                    grant_schema_sql(
                        p["privileges"],
                        p["schema_name_or_null"],
                        roles[p["grantee_role_id"]]["role_name"],
                        p["grant_option"],
                    )
                )
                db_ops.append(oid)
            elif op["operation_kind"] == "alter_database_setting":
                s = next(
                    x for x in ac["settings"] if x["setting_id"] == op["resource_id"]
                )
                lit = setting_literal(
                    s["normalized_value"], s["setting_name"], s["value_type"]
                )
                db_stmts.append(
                    alter_database_setting_sql(
                        db["database_name"], s["setting_name"], lit
                    )
                )
                db_ops.append(oid)
        if db_stmts:
            phases.append(
                {
                    "phase_index": idx,
                    "phase_kind": "database_transaction",
                    "database_id_or_null": db_id,
                    "transactional": True,
                    "connect_line": connect_line,
                    "statements": db_stmts,
                    "operation_ids": db_ops,
                    "requires_reload": False,
                    "requires_restart": False,
                }
            )
            idx += 1

    reload_stmts = []
    reload_ops = []
    for h in ac["hba_rows"]:
        reload_stmts.append(hba_comment(h))
    for oid in ac["topo"]:
        op = next(o for o in ac["operations"] if o["operation_id"] == oid)
        if op["operation_kind"] in ("emit_hba_rule", "reload_configuration"):
            reload_ops.append(oid)
    has_reload = (
        any(s["activation_mode"] == "reload" for s in ac["settings"]) or ac["hba_rows"]
    )
    has_restart = any(s["activation_mode"] == "restart" for s in ac["settings"])
    if has_reload:
        reload_stmts.append(reload_sql())
        phases.append(
            {
                "phase_index": idx,
                "phase_kind": "configuration_reload",
                "database_id_or_null": None,
                "transactional": False,
                "statements": reload_stmts,
                "operation_ids": reload_ops,
                "requires_reload": True,
                "requires_restart": has_restart,
            }
        )

    assigned = {oid for p in phases for oid in p.get("operation_ids", [])}
    attach = next(
        (p for p in phases if p["phase_kind"] == "database_transaction"), None
    )
    if attach is None:
        attach = next(
            (p for p in phases if p["phase_kind"] == "cluster_transaction"), None
        )
    if attach is not None:
        for oid in ac["topo"]:
            op = next(o for o in ac["operations"] if o["operation_id"] == oid)
            if op["operation_kind"] == "alter_role_setting" and oid not in assigned:
                attach["operation_ids"].append(oid)
                assigned.add(oid)

    return phases


def _phase_rows_for_cluster(cluster_id: str, phases: list[dict]) -> list[dict]:
    rows = []
    for p in phases:
        rows.append(
            {
                "cluster_id": cluster_id,
                "phase_index": p["phase_index"],
                "phase_kind": p["phase_kind"],
                "database_id_or_null": p.get("database_id_or_null"),
                "transactional": p.get("transactional", False),
                "operation_ids": list(p.get("operation_ids", [])),
                "requires_reload": bool(
                    p.get("requires_reload", p["phase_kind"] == "configuration_reload")
                ),
                "requires_restart": bool(p.get("requires_restart", False)),
            }
        )
    return rows


def compile_plan_dict(
    yaml_path: Path,
    toml_path: Path,
    ext_catalog_path: Path,
    setting_catalog_path: Path,
    policy_url: str,
) -> dict:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        sql_out = Path(td) / "bootstrap.sql"
        plan_out = Path(td) / "bootstrap_plan.json"
        rc = _run_planner_inner(
            Path(yaml_path),
            Path(toml_path),
            Path(ext_catalog_path),
            Path(setting_catalog_path),
            policy_url,
            sql_out,
            plan_out,
        )
        if rc != 0:
            raise RuntimeError("planner failed")
        return {
            "plan": json.loads(plan_out.read_text(encoding="utf-8")),
            "sql": sql_out.read_text(encoding="utf-8"),
            "sql_bytes": sql_out.read_bytes(),
        }
