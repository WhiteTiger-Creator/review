"""Independent Python chain oracle for X.509 path reconstruction."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_string(cert: dict[str, Any]) -> str:
    bc = cert.get("basic_constraints")
    is_ca_str = "true" if bc and bc.get("is_ca") else "false"
    if bc and bc.get("path_len_constraint") is not None:
        path_len_str = str(bc["path_len_constraint"])
    else:
        path_len_str = "null"

    nc = cert.get("name_constraints")
    if nc and nc.get("permitted_dns") is not None:
        permitted_str = ",".join(sorted(nc["permitted_dns"]))
    else:
        permitted_str = "null"

    if nc and nc.get("excluded_dns") is not None:
        excluded_str = ",".join(sorted(nc["excluded_dns"]))
    else:
        excluded_str = "null"

    policies = cert.get("certificate_policies")
    if policies is not None:
        policies_str = ",".join(sorted(policies))
    else:
        policies_str = "null"

    pc = cert.get("policy_constraints")
    if pc and pc.get("require_explicit_policy") is not None:
        require_policy_str = str(pc["require_explicit_policy"])
    else:
        require_policy_str = "null"

    validity = cert["validity"]
    return "|".join(
        [
            cert["id"],
            cert["subject"],
            cert["issuer"],
            cert["public_key"],
            str(validity["not_before"]),
            str(validity["not_after"]),
            is_ca_str,
            path_len_str,
            permitted_str,
            excluded_str,
            policies_str,
            require_policy_str,
        ]
    )


def verify_signature(cert: dict[str, Any], issuer_pub_key: str) -> bool:
    payload = canonical_string(cert) + issuer_pub_key
    expected = hashlib.sha256(payload.encode()).hexdigest()
    return cert["signature"] == expected


def compute_signature(cert: dict[str, Any], issuer_pub_key: str) -> str:
    payload = canonical_string(cert) + issuer_pub_key
    return hashlib.sha256(payload.encode()).hexdigest()


def extract_domain(subject: str) -> str | None:
    for part in subject.split(","):
        trimmed = part.strip()
        if trimmed.lower().startswith("cn="):
            return trimmed[3:]
    return None


def domain_matches(domain: str, pattern: str) -> bool:
    d_lower = domain.lower()
    p_lower = pattern.lower()
    if d_lower == p_lower:
        return True
    return d_lower.endswith(f".{p_lower}")


def validate_path(path: list[dict[str, Any]], roots: list[str], validation_time: int) -> bool:
    if not path:
        return False

    root = path[-1]
    if root["id"] not in roots:
        return False

    for cert in path:
        validity = cert["validity"]
        if validation_time < validity["not_before"] or validation_time > validity["not_after"]:
            return False

    for i in range(len(path) - 1):
        cert = path[i]
        issuer = path[i + 1]
        if cert["issuer"] != issuer["subject"]:
            return False
        if not verify_signature(cert, issuer["public_key"]):
            return False

    if not verify_signature(root, root["public_key"]):
        return False

    if not root.get("basic_constraints", {}).get("is_ca", False):
        return False

    for cert in path[1:-1]:
        if not cert.get("basic_constraints", {}).get("is_ca", False):
            return False

    for j in range(1, len(path)):
        cert = path[j]
        bc = cert.get("basic_constraints")
        if bc and bc.get("path_len_constraint") is not None:
            if (j - 1) > bc["path_len_constraint"]:
                return False

    leaf_domain = extract_domain(path[0]["subject"])
    if leaf_domain is None:
        return False

    for j in range(1, len(path)):
        cert = path[j]
        nc = cert.get("name_constraints")
        if not nc:
            continue
        permitted = nc.get("permitted_dns")
        if permitted:
            if not any(domain_matches(leaf_domain, p) for p in permitted):
                return False
        excluded = nc.get("excluded_dns")
        if excluded:
            if any(domain_matches(leaf_domain, e) for e in excluded):
                return False

    v: set[str] = set(root.get("certificate_policies") or [])
    for i in range(len(path) - 2, -1, -1):
        cert = path[i]
        p_i = set(cert.get("certificate_policies") or [])
        p_i_nonempty = bool(p_i)
        if not v:
            v = p_i
        elif "2.5.29.32.0" in v:
            v = p_i
        elif "2.5.29.32.0" in p_i:
            pass
        else:
            v = v & p_i
        if not v and p_i_nonempty:
            return False

    for j in range(1, len(path)):
        cert = path[j]
        pc = cert.get("policy_constraints")
        if not pc:
            continue
        require = pc.get("require_explicit_policy")
        if require is None:
            continue
        if j >= require:
            leaf_policies = path[0].get("certificate_policies") or []
            if not any(p != "2.5.29.32.0" for p in leaf_policies):
                return False

    return True


def _find_cert_by_id(pool: list[dict[str, Any]], cert_id: str) -> dict[str, Any] | None:
    for cert in pool:
        if cert["id"] == cert_id:
            return cert
    return None


def _collect_paths(
    curr_id: str,
    pool: list[dict[str, Any]],
    roots: list[str],
    validation_time: int,
    visited: set[str],
    current_path: list[dict[str, Any]],
    all_paths: list[list[str]],
) -> None:
    cert = _find_cert_by_id(pool, curr_id)
    if cert is None:
        return

    visited.add(curr_id)
    current_path.append(cert)

    if cert["id"] in roots:
        if validate_path(current_path, roots, validation_time):
            all_paths.append([c["id"] for c in current_path])
        current_path.pop()
        visited.remove(curr_id)
        return

    issuer_subject = cert["issuer"]
    candidates = sorted(
        (c for c in pool if c["subject"] == issuer_subject and c["id"] not in visited),
        key=lambda c: c["id"],
    )
    for candidate in candidates:
        _collect_paths(
            candidate["id"],
            pool,
            roots,
            validation_time,
            visited,
            current_path,
            all_paths,
        )

    current_path.pop()
    visited.remove(curr_id)


def find_path(
    target_id: str,
    pool: list[dict[str, Any]],
    roots: list[str],
    validation_time: int,
) -> list[str] | None:
    all_paths: list[list[str]] = []
    _collect_paths(target_id, pool, roots, validation_time, set(), [], all_paths)
    if not all_paths:
        return None
    return min(all_paths)


def reference_reconstruct_path(
    pool: list[dict[str, Any]],
    roots: list[str],
    target_id: str,
    validation_time: int,
) -> list[str] | None:
    return find_path(target_id, pool, roots, validation_time)


reconstruct_path = reference_reconstruct_path


def compute_pool_digest(pool: list[dict[str, Any]]) -> str:
    sorted_pool = sorted(pool, key=lambda c: c["id"])
    digest_input = "".join(canonical_string(cert) + "\n" for cert in sorted_pool)
    return hashlib.sha256(digest_input.encode()).hexdigest()


def load_json(path: str | Path) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)
