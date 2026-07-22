import base64
import copy
import hashlib
import hmac
import ipaddress
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


TASK_FILE = Path("/app/task_file")
SOURCE = Path("/app/workload_gate.go")

PUBLIC_HASHES = {
    "docs/workload_gate_contract.md": "fce7b938d9b065b62ae1ba0b2722c36f259ab637ee63e52d2a8bba0e2b4580c5",
    "input_data/mesh_policy.json": "20aafa58cbf93e13dbc64fb8e3021d851956d4a4125db7b88086e22c0aec8add",
    "input_data/workloads.json": "a13c9d37507dd99b2705de6d6ee311d6c9ab4f981a384bf46c9defb6c508122c",
    "input_data/approvers.json": "d478cd209b81f6698e4133011730fa452b1b2e096d3415b6845a76d26676cad0",
    "input_data/calls.jsonl": "7220786bcb701462d976e3cbb0afba8e178c28358836abbbad5af565fc4b0af2",
}

REASONS = [
    "unknown-source",
    "unknown-subject",
    "unknown-route",
    "source-blocked",
    "subject-blocked",
    "untrusted-domain",
    "identity-mismatch",
    "route-mismatch",
    "subject-not-allowed",
    "cluster-not-allowed",
    "env-not-allowed",
    "attestation-too-low",
    "scope-missing",
    "assertion-malformed",
    "assertion-claim-mismatch",
    "assertion-expired",
    "audience-not-allowed",
    "bad-signature",
    "delegation-not-allowed",
    "delegation-invalid",
    "delegation-scope-missing",
    "network-too-risky",
    "approval-invalid",
    "approval-missing",
    "nonce-replay",
]

ASSERTION_KEYS = {
    "request_id",
    "source_id",
    "subject_id",
    "route_id",
    "key_id",
    "method",
    "path",
    "audience",
    "nonce",
    "issued_at",
    "scopes",
}

DECISION_KEYS = {
    "request_id",
    "decision",
    "reasons",
    "route_id",
    "source_id",
    "subject_id",
    "network_risk",
    "effective_scopes",
    "accepted_delegation_ids",
    "valid_approval_ids",
    "authorization_expires_at",
}

SUMMARY_KEYS = {
    "total_requests",
    "allowed",
    "denied",
    "allowed_request_ids",
    "denied_request_ids",
    "reason_counts",
}

FRONTEND = "spiffe://prod.example/ns/shop/sa/frontend"
ORDERS = "spiffe://prod.example/ns/shop/sa/orders"
ADMIN = "spiffe://prod.example/ns/platform/sa/admin-console"
BATCH = "spiffe://prod.example/ns/jobs/sa/nightly-batch"
CANARY = "spiffe://prod.example/ns/shop/sa/canary"
QUARANTINED = "spiffe://prod.example/ns/shop/sa/old-worker"

VARIANTS = [
    "breakglass_allowed",
    "two_hop_delegation_allowed",
    "delegation_hop_limit",
    "delegation_disallowed_payment",
    "delegation_scope_intersection",
    "approval_distinct_approvers",
    "approval_bad_signature",
    "assertion_claim_mismatch",
    "bad_call_signature",
    "expired_bad_audience",
    "unknown_principals_and_route",
    "quarantined_direct_with_delegation",
    "identity_mismatch",
    "network_default_route_mismatch",
    "nonce_replay_after_denied",
    "subject_group_denied",
    "rotated_key_valid_at_issued",
    "inactive_workload_key_bad_signature",
    "scope_implication_delegated_allowed",
    "scope_implication_cycle",
    "most_specific_network_zone",
    "repeated_approval_role_quorum_allowed",
    "repeated_approval_role_quorum_denied",
    "assertion_null_scopes_malformed",
    "approval_backtracking_quorum_allowed",
]


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def fmt_time(value):
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def b64d(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def b64u(data):
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def b64json(obj):
    return b64u(json.dumps(obj, separators=(",", ":"), sort_keys=True).encode())


def hmac_b64(secret_b64url, message):
    return b64u(hmac.new(b64d(secret_b64url), message.encode(), hashlib.sha256).digest())


def hmac_ok(secret_b64url, message, got):
    try:
        expected = hmac_b64(secret_b64url, message)
    except Exception:
        return False
    return hmac.compare_digest(expected, got)


def norm(values):
    return sorted({value for value in values if isinstance(value, str) and value})


def set_has_all(required, have):
    have_set = set(have)
    return all(value in have_set for value in norm(required))


def expand_scopes(policy, values):
    expanded = set(norm(values))
    stack = list(expanded)
    implications = policy.get("scope_implications", {})
    while stack:
        scope = stack.pop()
        for implied in implications.get(scope, []):
            if isinstance(implied, str) and implied and implied not in expanded:
                expanded.add(implied)
                stack.append(implied)
    return sorted(expanded)


def overlap(left, right):
    return bool(set(left).intersection(right))


def read_json(path):
    with path.open() as handle:
        return json.load(handle)


def read_jsonl(path):
    rows = []
    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_case(case, path):
    path.mkdir(parents=True, exist_ok=True)
    with (path / "mesh_policy.json").open("w") as handle:
        json.dump(case["policy"], handle, separators=(",", ":"), sort_keys=True)
        handle.write("\n")
    with (path / "workloads.json").open("w") as handle:
        json.dump({"workloads": case["workloads"]}, handle, separators=(",", ":"), sort_keys=True)
        handle.write("\n")
    with (path / "approvers.json").open("w") as handle:
        json.dump(case["approvers"], handle, separators=(",", ":"), sort_keys=True)
        handle.write("\n")
    with (path / "calls.jsonl").open("w") as handle:
        for row in case["calls"]:
            json.dump(row, handle, separators=(",", ":"), sort_keys=True)
            handle.write("\n")


def load_case(path):
    return {
        "policy": read_json(path / "mesh_policy.json"),
        "workloads": read_json(path / "workloads.json")["workloads"],
        "approvers": read_json(path / "approvers.json"),
        "calls": read_jsonl(path / "calls.jsonl"),
    }


def workload_map(case):
    return {row["spiffe_id"]: row for row in case["workloads"]}


def approver_map(case):
    return {row["approver_id"]: row for row in case["approvers"]}


def key_secret(entity, key_id=None):
    keys = entity.get("keys", [])
    if not keys:
        return entity.get("secret_b64url")
    if key_id is None:
        return keys[0]["secret_b64url"]
    for key in keys:
        if key.get("key_id") == key_id:
            return key["secret_b64url"]
    raise KeyError(key_id)


def active_key_secret(entity, key_id, at):
    for key in entity.get("keys", []):
        try:
            not_before = parse_time(key["not_before"])
            expires_at = parse_time(key["expires_at"])
        except Exception:
            continue
        if (
            key.get("key_id") == key_id
            and key.get("status") == "active"
            and not_before <= at < expires_at
        ):
            return key["secret_b64url"]
    return None


def key_active_at(entity, at):
    for key in entity.get("keys", []):
        try:
            if key.get("status") == "active" and parse_time(key["not_before"]) <= at < parse_time(key["expires_at"]):
                return key["key_id"]
        except Exception:
            pass
    return entity.get("keys", [{"key_id": "missing-key"}])[0]["key_id"]


def workload_secret(case, spiffe_id, key_id=None):
    workload = workload_map(case).get(spiffe_id)
    if workload is None:
        return b64u(b"unknown workload")
    return key_secret(workload, key_id)


def approver_secret(case, approver_id, key_id=None):
    return key_secret(approver_map(case)[approver_id], key_id)


def make_call(case, request_id, source_id, subject_id, route_id, method, path, audience, nonce, origin_ip, issued_at, scopes, delegations=None, approvals=None, assertion_updates=None, tamper_signature=False, key_id=None):
    source = workload_map(case).get(source_id)
    if key_id is None:
        key_id = key_active_at(source, parse_time(issued_at)) if source is not None else "missing-key"
    assertion = {
        "request_id": request_id,
        "source_id": source_id,
        "subject_id": subject_id,
        "route_id": route_id,
        "key_id": key_id,
        "method": method,
        "path": path,
        "audience": audience,
        "nonce": nonce,
        "issued_at": issued_at,
        "scopes": scopes,
    }
    if assertion_updates:
        assertion.update(assertion_updates)
    assertion_b64 = b64json(assertion)
    signing = "\n".join([request_id, source_id, key_id, assertion_b64, nonce])
    signature = hmac_b64(workload_secret(case, source_id, key_id), signing)
    if tamper_signature:
        signature = "A" + signature[1:]
    return {
        "request_id": request_id,
        "route_id": route_id,
        "source_id": source_id,
        "subject_id": subject_id,
        "key_id": key_id,
        "method": method,
        "path": path,
        "audience": audience,
        "nonce": nonce,
        "origin_ip": origin_ip,
        "assertion_b64url": assertion_b64,
        "signature_b64url": signature,
        "delegations": delegations or [],
        "approvals": approvals or [],
    }


def make_grant(case, request_id, grant_id, from_id, to_id, scopes, not_before, expires_at, tamper=False, key_id=None):
    from_workload = workload_map(case).get(from_id)
    if key_id is None:
        key_id = key_active_at(from_workload, parse_time(not_before)) if from_workload is not None else "missing-key"
    signing = "\n".join([grant_id, request_id, from_id, to_id, key_id, ",".join(norm(scopes)), not_before, expires_at])
    signature = hmac_b64(workload_secret(case, from_id, key_id), signing)
    if tamper:
        signature = signature[:-1] + ("A" if signature[-1] != "A" else "B")
    return {
        "grant_id": grant_id,
        "from": from_id,
        "to": to_id,
        "key_id": key_id,
        "scopes": scopes,
        "not_before": not_before,
        "expires_at": expires_at,
        "signature_b64url": signature,
    }


def make_approval(case, request_id, approval_id, approver_id, role, decision, issued_at, expires_at, ticket, tamper=False, key_id=None):
    approver = approver_map(case)[approver_id]
    if key_id is None:
        key_id = key_active_at(approver, parse_time(issued_at))
    signing = "\n".join([approval_id, request_id, approver_id, key_id, role, decision, issued_at, expires_at, ticket])
    signature = hmac_b64(approver_secret(case, approver_id, key_id), signing)
    if tamper:
        signature = "B" + signature[1:]
    return {
        "approval_id": approval_id,
        "approver_id": approver_id,
        "key_id": key_id,
        "role": role,
        "decision": decision,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "ticket": ticket,
        "signature_b64url": signature,
    }


def decode_assertion(text):
    try:
        obj = json.loads(b64d(text).decode())
    except Exception:
        return None, None
    if not isinstance(obj, dict) or set(obj) != ASSERTION_KEYS:
        return None, None
    for key in ASSERTION_KEYS - {"scopes"}:
        if not isinstance(obj.get(key), str) or obj[key] == "":
            return None, None
    if not isinstance(obj.get("scopes"), list) or not all(isinstance(value, str) and value for value in obj["scopes"]):
        return None, None
    try:
        issued_at = parse_time(obj["issued_at"])
    except Exception:
        return None, None
    return obj, issued_at


def identity_matches(workload):
    return workload["spiffe_id"] == f"spiffe://{workload['trust_domain']}/ns/{workload['namespace']}/sa/{workload['service']}"


def attestation_rank(value):
    return {"none": 0, "baseline": 1, "hardware": 2}.get(value, 0)


def network_risk(policy, ip_text):
    try:
        ip = ipaddress.ip_address(ip_text)
    except ValueError:
        return policy["default_network_risk"]
    best_prefix = -1
    best_risk = policy["default_network_risk"]
    for zone in policy["network_zones"]:
        network = ipaddress.ip_network(zone["cidr"])
        if ip in network and network.prefixlen > best_prefix:
            best_prefix = network.prefixlen
            best_risk = zone["risk"]
    return best_risk


def intersect(left, right):
    right_set = set(right)
    return [value for value in norm(left) if value in right_set]


def validate_chain(call, route, workloads, trusted, as_of, policy):
    if not call["delegations"]:
        return False, [], [], []
    if route is not None and len(call["delegations"]) > route["max_delegation_hops"]:
        return False, [], [], []
    expected_from = call["subject_id"]
    accepted_ids = []
    expiries = []
    hop_scopes = None
    for grant in call["delegations"]:
        if not all(grant.get(key) for key in ("grant_id", "from", "to", "key_id", "not_before", "expires_at")):
            return False, [], [], []
        if grant["from"] != expected_from:
            return False, [], [], []
        from_workload = workloads.get(grant["from"])
        to_workload = workloads.get(grant["to"])
        if not from_workload or not to_workload:
            return False, [], [], []
        if from_workload["status"] != "active" or to_workload["status"] != "active":
            return False, [], [], []
        if from_workload["trust_domain"] not in trusted or to_workload["trust_domain"] not in trusted:
            return False, [], [], []
        try:
            not_before = parse_time(grant["not_before"])
            expires_at = parse_time(grant["expires_at"])
        except Exception:
            return False, [], [], []
        if not (not_before <= as_of < expires_at):
            return False, [], [], []
        signed_scopes = norm(grant.get("scopes", []))
        if not signed_scopes:
            return False, [], [], []
        signing = "\n".join([
            grant["grant_id"],
            call["request_id"],
            grant["from"],
            grant["to"],
            grant.get("key_id", ""),
            ",".join(signed_scopes),
            grant["not_before"],
            grant["expires_at"],
        ])
        secret = active_key_secret(from_workload, grant.get("key_id", ""), not_before)
        if secret is None or not hmac_ok(secret, signing, grant.get("signature_b64url", "")):
            return False, [], [], []
        scopes = expand_scopes(policy, signed_scopes)
        hop_scopes = scopes if hop_scopes is None else intersect(hop_scopes, scopes)
        accepted_ids.append(grant["grant_id"])
        expiries.append(expires_at)
        expected_from = grant["to"]
    if expected_from != call["source_id"]:
        return False, [], [], []
    return True, accepted_ids, hop_scopes or [], expiries


def valid_approvals(call, approvers, as_of):
    valid = []
    any_invalid = False
    for approval in call["approvals"]:
        approver = approvers.get(approval.get("approver_id"))
        try:
            issued_at = parse_time(approval["issued_at"])
            expires_at = parse_time(approval["expires_at"])
        except Exception:
            issued_at = expires_at = None
        ok = (
            approver is not None
            and approver["status"] == "active"
            and approval.get("decision") == "approve"
            and approval.get("role") in approver["roles"]
            and issued_at is not None
            and issued_at <= as_of < expires_at
        )
        if ok:
            signing = "\n".join([
                approval["approval_id"],
                call["request_id"],
                approval["approver_id"],
                approval.get("key_id", ""),
                approval["role"],
                approval["decision"],
                approval["issued_at"],
                approval["expires_at"],
                approval["ticket"],
            ])
            secret = active_key_secret(approver, approval.get("key_id", ""), issued_at)
            ok = secret is not None and hmac_ok(secret, signing, approval.get("signature_b64url", ""))
        if ok:
            valid.append({"approval": approval, "expires": expires_at})
        else:
            any_invalid = True
    return valid, any_invalid


def approval_coverage(required_roles, approvals):
    if not required_roles:
        return True
    used = set()

    def search(index):
        if index == len(required_roles):
            return True
        role = required_roles[index]
        for item in approvals:
            approval = item["approval"]
            if approval["role"] == role and approval["approver_id"] not in used:
                used.add(approval["approver_id"])
                if search(index + 1):
                    return True
                used.remove(approval["approver_id"])
        return False

    return search(0)


def solve_case(input_dir):
    policy = read_json(input_dir / "mesh_policy.json")
    workloads = workload_map(load_case(input_dir))
    approvers = approver_map(load_case(input_dir))
    calls = read_jsonl(input_dir / "calls.jsonl")
    as_of = parse_time(policy["as_of"])
    trusted = set(policy["trusted_domains"])
    seen_nonce = set()
    rows = []
    reason_counts = {reason: 0 for reason in REASONS}
    allowed_ids = []
    denied_ids = []

    for call in calls:
        flags = set()
        source = workloads.get(call["source_id"])
        subject = workloads.get(call["subject_id"])
        route = policy["routes"].get(call["route_id"])

        if source is None:
            flags.add("unknown-source")
        if subject is None:
            flags.add("unknown-subject")
        if route is None:
            flags.add("unknown-route")
        if source is not None and source["status"] != "active":
            flags.add("source-blocked")
        if subject is not None and subject["status"] != "active":
            flags.add("subject-blocked")
        if (source is not None and source["trust_domain"] not in trusted) or (subject is not None and subject["trust_domain"] not in trusted):
            flags.add("untrusted-domain")
        if (source is not None and not identity_matches(source)) or (subject is not None and not identity_matches(subject)):
            flags.add("identity-mismatch")

        risk = network_risk(policy, call["origin_ip"])
        if route is not None:
            if call["method"] != route["method"] or not call["path"].startswith(route["path_prefix"]):
                flags.add("route-mismatch")
            if subject is not None and not overlap(subject["groups"], route["allowed_subject_groups"]):
                flags.add("subject-not-allowed")
            if source is not None and source["cluster"] not in route["allowed_source_clusters"]:
                flags.add("cluster-not-allowed")
            if source is not None and source["env"] not in route["allowed_envs"]:
                flags.add("env-not-allowed")
            if source is not None and attestation_rank(source["attestation"]) < attestation_rank(route["require_attestation"]):
                flags.add("attestation-too-low")
            if risk > route["max_network_risk"]:
                flags.add("network-too-risky")

        assertion, issued_at = decode_assertion(call["assertion_b64url"])
        assertion_scopes = []
        if assertion is None:
            flags.add("assertion-malformed")
        else:
            assertion_scopes = expand_scopes(policy, assertion["scopes"])
            for key in ("request_id", "source_id", "subject_id", "route_id", "key_id", "method", "path", "audience", "nonce"):
                if assertion[key] != call[key]:
                    flags.add("assertion-claim-mismatch")
                    break
            if route is not None and (issued_at > as_of or (as_of - issued_at).total_seconds() > route["max_assertion_age_seconds"]):
                flags.add("assertion-expired")
        if call["audience"] not in policy["allowed_audiences"]:
            flags.add("audience-not-allowed")
        if source is not None and assertion is not None:
            signing = "\n".join([call["request_id"], call["source_id"], call.get("key_id", ""), call["assertion_b64url"], call["nonce"]])
            secret = active_key_secret(source, call.get("key_id", ""), issued_at)
            if secret is None or not hmac_ok(secret, signing, call["signature_b64url"]):
                flags.add("bad-signature")
        if route is not None and not set_has_all(route["required_scopes"], assertion_scopes):
            flags.add("scope-missing")

        effective_scopes = assertion_scopes[:] if assertion is not None else []
        accepted_delegations = []
        delegation_expiries = []
        if call["source_id"] == call["subject_id"]:
            if call["delegations"]:
                flags.add("delegation-invalid")
        else:
            if route is not None and not route["allow_delegation"]:
                flags.add("delegation-not-allowed")
            chain_valid, ids, hop_scopes, expiries = validate_chain(call, route, workloads, trusted, as_of, policy)
            if not chain_valid:
                flags.add("delegation-invalid")
                effective_scopes = []
            else:
                effective_scopes = intersect(effective_scopes, hop_scopes) if assertion is not None else []
                delegation_expiries = expiries
                if route is not None and not set_has_all(route["required_scopes"], hop_scopes):
                    flags.add("delegation-scope-missing")
                if route is not None and route["allow_delegation"]:
                    accepted_delegations = ids

        approvals, any_invalid_approval = valid_approvals(call, approvers, as_of)
        if any_invalid_approval:
            flags.add("approval-invalid")
        valid_approval_ids = sorted(item["approval"]["approval_id"] for item in approvals)
        if route is not None and not approval_coverage(route["required_approval_roles"], approvals):
            flags.add("approval-missing")

        nonce_key = (call["source_id"], call["audience"], call["nonce"])
        if nonce_key in seen_nonce:
            flags.add("nonce-replay")
        seen_nonce.add(nonce_key)

        reasons = [reason for reason in REASONS if reason in flags]
        if reasons:
            decision = "deny"
            expires = None
            denied_ids.append(call["request_id"])
        else:
            decision = "allow"
            expiry = issued_at + timedelta(seconds=route["max_assertion_age_seconds"])
            for grant_expiry in delegation_expiries:
                expiry = min(expiry, grant_expiry)
            required = set(route["required_approval_roles"])
            for item in approvals:
                if item["approval"]["role"] in required:
                    expiry = min(expiry, item["expires"])
            expires = fmt_time(expiry)
            allowed_ids.append(call["request_id"])
        for reason in reasons:
            reason_counts[reason] += 1
        rows.append({
            "request_id": call["request_id"],
            "decision": decision,
            "reasons": reasons,
            "route_id": call["route_id"],
            "source_id": call["source_id"],
            "subject_id": call["subject_id"],
            "network_risk": risk,
            "effective_scopes": effective_scopes,
            "accepted_delegation_ids": accepted_delegations,
            "valid_approval_ids": valid_approval_ids,
            "authorization_expires_at": expires,
        })

    summary = {
        "total_requests": len(calls),
        "allowed": len(allowed_ids),
        "denied": len(denied_ids),
        "allowed_request_ids": allowed_ids,
        "denied_request_ids": denied_ids,
        "reason_counts": reason_counts,
    }
    return rows, summary


def run_gate(binary, input_dir, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(binary), str(input_dir), str(output_dir)], check=True, cwd="/app", timeout=30)
    return read_jsonl(output_dir / "workload_decisions.jsonl"), read_json(output_dir / "workload_summary.json")


def validate_output_schema(rows, summary):
    assert set(summary) == SUMMARY_KEYS
    assert isinstance(summary["total_requests"], int)
    assert isinstance(summary["allowed"], int)
    assert isinstance(summary["denied"], int)
    assert isinstance(summary["allowed_request_ids"], list)
    assert isinstance(summary["denied_request_ids"], list)
    assert set(summary["reason_counts"]) == set(REASONS)
    assert all(isinstance(summary["reason_counts"][reason], int) for reason in REASONS)
    assert summary["total_requests"] == len(rows)
    assert summary["allowed"] + summary["denied"] == len(rows)
    for row in rows:
        assert set(row) == DECISION_KEYS
        assert row["decision"] in {"allow", "deny"}
        assert isinstance(row["request_id"], str)
        assert isinstance(row["route_id"], str)
        assert isinstance(row["source_id"], str)
        assert isinstance(row["subject_id"], str)
        assert isinstance(row["network_risk"], int)
        for key in ("reasons", "effective_scopes", "accepted_delegation_ids", "valid_approval_ids"):
            assert isinstance(row[key], list)
            assert all(isinstance(value, str) for value in row[key])
        assert row["reasons"] == [reason for reason in REASONS if reason in row["reasons"]]
        assert len(row["reasons"]) == len(set(row["reasons"]))
        assert row["effective_scopes"] == sorted(row["effective_scopes"])
        assert row["valid_approval_ids"] == sorted(row["valid_approval_ids"])
        if row["decision"] == "deny":
            assert row["authorization_expires_at"] is None
            assert row["reasons"]
        else:
            assert isinstance(row["authorization_expires_at"], str)
            assert row["reasons"] == []


def base_case():
    return load_case(TASK_FILE / "input_data")


def variant_case(name):
    case = copy.deepcopy(base_case())
    case["calls"] = []
    if name == "breakglass_allowed":
        req = "var-001"
        approvals = [
            make_approval(case, req, "var-appr-001a", "incident-1", "incident-commander", "approve", "2026-07-20T11:58:00Z", "2026-07-20T12:06:00Z", "INC-1"),
            make_approval(case, req, "var-appr-001b", "sec-1", "security", "approve", "2026-07-20T11:58:10Z", "2026-07-20T12:07:00Z", "INC-1"),
        ]
        case["calls"].append(make_call(case, req, ADMIN, ADMIN, "breakglass-admin", "POST", "/admin/breakglass", "mesh-gateway", "var-nonce-1", "10.42.2.3", "2026-07-20T11:59:30Z", ["admin:breakglass"], approvals=approvals))
    elif name == "two_hop_delegation_allowed":
        req = "var-002"
        grants = [
            make_grant(case, req, "var-grant-002a", FRONTEND, BATCH, ["orders:read", "cart:read"], "2026-07-20T11:56:00Z", "2026-07-20T12:03:00Z"),
            make_grant(case, req, "var-grant-002b", BATCH, ORDERS, ["orders:read"], "2026-07-20T11:56:10Z", "2026-07-20T12:04:00Z"),
        ]
        case["calls"].append(make_call(case, req, ORDERS, FRONTEND, "orders-read", "GET", "/orders/variant-2", "orders-api", "var-nonce-2", "10.77.3.4", "2026-07-20T11:59:00Z", ["orders:read", "cart:read"], delegations=grants))
    elif name == "delegation_hop_limit":
        case["policy"]["routes"]["orders-read"]["max_delegation_hops"] = 1
        req = "var-003"
        grants = [
            make_grant(case, req, "var-grant-003a", FRONTEND, BATCH, ["orders:read"], "2026-07-20T11:56:00Z", "2026-07-20T12:03:00Z"),
            make_grant(case, req, "var-grant-003b", BATCH, ORDERS, ["orders:read"], "2026-07-20T11:56:10Z", "2026-07-20T12:04:00Z"),
        ]
        case["calls"].append(make_call(case, req, ORDERS, FRONTEND, "orders-read", "GET", "/orders/variant-3", "mesh-gateway", "var-nonce-3", "10.42.3.4", "2026-07-20T11:59:00Z", ["orders:read"], delegations=grants))
    elif name == "delegation_disallowed_payment":
        req = "var-004"
        grants = [make_grant(case, req, "var-grant-004a", ADMIN, ORDERS, ["payments:write", "audit:append"], "2026-07-20T11:56:00Z", "2026-07-20T12:05:00Z")]
        approvals = [
            make_approval(case, req, "var-appr-004a", "sec-1", "security", "approve", "2026-07-20T11:57:00Z", "2026-07-20T12:05:00Z", "PAY-4"),
            make_approval(case, req, "var-appr-004b", "pay-1", "payments-owner", "approve", "2026-07-20T11:57:10Z", "2026-07-20T12:05:00Z", "PAY-4"),
        ]
        case["calls"].append(make_call(case, req, ORDERS, ADMIN, "payments-write", "POST", "/payments/variant-4", "mesh-gateway", "var-nonce-4", "10.42.4.4", "2026-07-20T11:59:30Z", ["payments:write", "audit:append"], delegations=grants, approvals=approvals))
    elif name == "delegation_scope_intersection":
        req = "var-005"
        grants = [make_grant(case, req, "var-grant-005a", FRONTEND, ORDERS, ["cart:read"], "2026-07-20T11:56:00Z", "2026-07-20T12:05:00Z")]
        case["calls"].append(make_call(case, req, ORDERS, FRONTEND, "orders-read", "GET", "/orders/variant-5", "orders-api", "var-nonce-5", "10.42.5.4", "2026-07-20T11:59:00Z", ["orders:read"], delegations=grants))
    elif name == "approval_distinct_approvers":
        case["approvers"].append({
            "approver_id": "dual-1",
            "roles": ["payments-owner", "security"],
            "status": "active",
            "keys": [{
                "key_id": "dual-2026",
                "secret_b64url": b64u(b"dual approver secret"),
                "status": "active",
                "not_before": "2026-07-01T00:00:00Z",
                "expires_at": "2026-08-01T00:00:00Z",
            }],
        })
        req = "var-006"
        approvals = [
            make_approval(case, req, "var-appr-006a", "dual-1", "security", "approve", "2026-07-20T11:57:00Z", "2026-07-20T12:05:00Z", "PAY-6"),
            make_approval(case, req, "var-appr-006b", "dual-1", "payments-owner", "approve", "2026-07-20T11:57:10Z", "2026-07-20T12:05:00Z", "PAY-6"),
        ]
        case["calls"].append(make_call(case, req, ADMIN, ADMIN, "payments-write", "POST", "/payments/variant-6", "mesh-gateway", "var-nonce-6", "10.42.6.4", "2026-07-20T11:59:30Z", ["payments:write", "audit:append"], approvals=approvals))
    elif name == "approval_bad_signature":
        req = "var-007"
        approvals = [
            make_approval(case, req, "var-appr-007a", "sec-1", "security", "approve", "2026-07-20T11:57:00Z", "2026-07-20T12:05:00Z", "PAY-7"),
            make_approval(case, req, "var-appr-007b", "pay-1", "payments-owner", "approve", "2026-07-20T11:57:10Z", "2026-07-20T12:05:00Z", "PAY-7", tamper=True),
        ]
        case["calls"].append(make_call(case, req, ADMIN, ADMIN, "payments-write", "POST", "/payments/variant-7", "mesh-gateway", "var-nonce-7", "10.42.7.4", "2026-07-20T11:59:30Z", ["payments:write", "audit:append"], approvals=approvals))
    elif name == "assertion_claim_mismatch":
        case["calls"].append(make_call(case, "var-008", FRONTEND, FRONTEND, "orders-read", "GET", "/orders/visible", "mesh-gateway", "var-nonce-8", "10.42.8.4", "2026-07-20T11:59:30Z", ["orders:read"], assertion_updates={"path": "/orders/signed"}))
    elif name == "bad_call_signature":
        case["calls"].append(make_call(case, "var-009", FRONTEND, FRONTEND, "orders-read", "GET", "/orders/variant-9", "mesh-gateway", "var-nonce-9", "10.42.9.4", "2026-07-20T11:59:30Z", ["orders:read"], tamper_signature=True))
    elif name == "expired_bad_audience":
        case["calls"].append(make_call(case, "var-010", FRONTEND, FRONTEND, "orders-read", "GET", "/orders/variant-10", "sidecar-debug", "var-nonce-10", "10.42.10.4", "2026-07-20T11:50:00Z", ["orders:read"]))
    elif name == "unknown_principals_and_route":
        missing_source = "spiffe://prod.example/ns/missing/sa/source"
        missing_subject = "spiffe://prod.example/ns/missing/sa/subject"
        case["calls"].append(make_call(case, "var-011", missing_source, missing_subject, "route-missing", "GET", "/missing", "mesh-gateway", "var-nonce-11", "10.42.11.4", "2026-07-20T11:59:30Z", ["orders:read"]))
    elif name == "quarantined_direct_with_delegation":
        req = "var-012"
        grants = [make_grant(case, req, "var-grant-012a", FRONTEND, ORDERS, ["orders:read"], "2026-07-20T11:56:00Z", "2026-07-20T12:05:00Z")]
        case["calls"].append(make_call(case, req, QUARANTINED, QUARANTINED, "orders-read", "GET", "/orders/variant-12", "mesh-gateway", "var-nonce-12", "10.42.12.4", "2026-07-20T11:59:30Z", ["orders:read"], delegations=grants))
    elif name == "identity_mismatch":
        for workload in case["workloads"]:
            if workload["spiffe_id"] == FRONTEND:
                workload["namespace"] = "wrong"
        case["calls"].append(make_call(case, "var-013", FRONTEND, FRONTEND, "orders-read", "GET", "/orders/variant-13", "mesh-gateway", "var-nonce-13", "10.42.13.4", "2026-07-20T11:59:30Z", ["orders:read"]))
    elif name == "network_default_route_mismatch":
        case["calls"].append(make_call(case, "var-014", FRONTEND, FRONTEND, "orders-read", "GET", "/inventory/variant-14", "mesh-gateway", "var-nonce-14", "203.0.113.14", "2026-07-20T11:59:30Z", ["orders:read"]))
    elif name == "nonce_replay_after_denied":
        case["calls"].append(make_call(case, "var-015a", FRONTEND, FRONTEND, "orders-read", "GET", "/orders/variant-15a", "mesh-gateway", "var-nonce-15", "10.42.15.4", "2026-07-20T11:59:30Z", ["orders:read"], tamper_signature=True))
        case["calls"].append(make_call(case, "var-015b", FRONTEND, FRONTEND, "orders-read", "GET", "/orders/variant-15b", "mesh-gateway", "var-nonce-15", "10.42.15.5", "2026-07-20T11:59:40Z", ["orders:read"]))
    elif name == "subject_group_denied":
        case["calls"].append(make_call(case, "var-016", BATCH, BATCH, "orders-read", "GET", "/orders/variant-16", "mesh-gateway", "var-nonce-16", "10.77.16.4", "2026-07-20T11:59:30Z", ["orders:read"]))
    elif name == "rotated_key_valid_at_issued":
        case["calls"].append(make_call(case, "var-017", FRONTEND, FRONTEND, "orders-read", "GET", "/orders/variant-17", "mesh-gateway", "var-nonce-17", "10.42.17.4", "2026-07-20T11:59:20Z", ["orders:read"], key_id="frontend-previous"))
    elif name == "inactive_workload_key_bad_signature":
        case["calls"].append(make_call(case, "var-018", FRONTEND, FRONTEND, "orders-read", "GET", "/orders/variant-18", "mesh-gateway", "var-nonce-18", "10.42.18.4", "2026-07-20T11:59:30Z", ["orders:read"], key_id="frontend-disabled"))
    elif name == "scope_implication_delegated_allowed":
        req = "var-019"
        grants = [make_grant(case, req, "var-grant-019a", FRONTEND, ORDERS, ["orders:*"], "2026-07-20T11:56:00Z", "2026-07-20T12:04:30Z")]
        case["calls"].append(make_call(case, req, ORDERS, FRONTEND, "orders-read", "GET", "/orders/variant-19", "orders-api", "var-nonce-19", "10.77.19.4", "2026-07-20T11:59:05Z", ["orders:*"], delegations=grants))
    elif name == "scope_implication_cycle":
        case["policy"]["scope_implications"]["cycle:a"] = ["cycle:b"]
        case["policy"]["scope_implications"]["cycle:b"] = ["cycle:a", "orders:read"]
        case["calls"].append(make_call(case, "var-020", FRONTEND, FRONTEND, "orders-read", "GET", "/orders/variant-20", "mesh-gateway", "var-nonce-20", "10.42.20.4", "2026-07-20T11:59:30Z", ["cycle:a"]))
    elif name == "most_specific_network_zone":
        case["policy"]["network_zones"].append({"cidr": "10.42.44.0/24", "risk": 4})
        case["calls"].append(make_call(case, "var-021", FRONTEND, FRONTEND, "orders-read", "GET", "/orders/variant-21", "mesh-gateway", "var-nonce-21", "10.42.44.9", "2026-07-20T11:59:30Z", ["orders:read"]))
    elif name == "repeated_approval_role_quorum_allowed":
        case["policy"]["routes"]["breakglass-admin"]["required_approval_roles"] = ["incident-commander", "security", "security"]
        case["approvers"].append({
            "approver_id": "sec-2",
            "roles": ["security"],
            "status": "active",
            "keys": [{
                "key_id": "sec-2-2026",
                "secret_b64url": b64u(b"second security approver secret"),
                "status": "active",
                "not_before": "2026-07-01T00:00:00Z",
                "expires_at": "2026-08-01T00:00:00Z",
            }],
        })
        req = "var-022"
        approvals = [
            make_approval(case, req, "var-appr-022a", "incident-1", "incident-commander", "approve", "2026-07-20T11:58:00Z", "2026-07-20T12:06:00Z", "INC-22"),
            make_approval(case, req, "var-appr-022b", "sec-1", "security", "approve", "2026-07-20T11:58:10Z", "2026-07-20T12:07:00Z", "INC-22"),
            make_approval(case, req, "var-appr-022c", "sec-2", "security", "approve", "2026-07-20T11:58:20Z", "2026-07-20T12:08:00Z", "INC-22"),
        ]
        case["calls"].append(make_call(case, req, ADMIN, ADMIN, "breakglass-admin", "POST", "/admin/breakglass", "mesh-gateway", "var-nonce-22", "10.42.22.4", "2026-07-20T11:59:30Z", ["admin:*"], approvals=approvals))
    elif name == "repeated_approval_role_quorum_denied":
        case["policy"]["routes"]["breakglass-admin"]["required_approval_roles"] = ["incident-commander", "security", "security"]
        req = "var-023"
        approvals = [
            make_approval(case, req, "var-appr-023a", "incident-1", "incident-commander", "approve", "2026-07-20T11:58:00Z", "2026-07-20T12:06:00Z", "INC-23"),
            make_approval(case, req, "var-appr-023b", "sec-1", "security", "approve", "2026-07-20T11:58:10Z", "2026-07-20T12:07:00Z", "INC-23"),
            make_approval(case, req, "var-appr-023c", "sec-1", "security", "approve", "2026-07-20T11:58:20Z", "2026-07-20T12:08:00Z", "INC-23"),
        ]
        case["calls"].append(make_call(case, req, ADMIN, ADMIN, "breakglass-admin", "POST", "/admin/breakglass", "mesh-gateway", "var-nonce-23", "10.42.23.4", "2026-07-20T11:59:30Z", ["admin:*"], approvals=approvals))
    elif name == "assertion_null_scopes_malformed":
        case["calls"].append(make_call(case, "var-024", FRONTEND, FRONTEND, "orders-read", "GET", "/orders/variant-24", "mesh-gateway", "var-nonce-24", "10.42.24.4", "2026-07-20T11:59:30Z", ["orders:read"], assertion_updates={"scopes": None}))
    elif name == "approval_backtracking_quorum_allowed":
        case["policy"]["routes"]["payments-write"]["required_approval_roles"] = ["security", "payments-owner"]
        case["approvers"].append({
            "approver_id": "dual-2",
            "roles": ["security", "payments-owner"],
            "status": "active",
            "keys": [{
                "key_id": "dual-2-2026",
                "secret_b64url": b64u(b"second dual approver secret"),
                "status": "active",
                "not_before": "2026-07-01T00:00:00Z",
                "expires_at": "2026-08-01T00:00:00Z",
            }],
        })
        req = "var-025"
        approvals = [
            make_approval(case, req, "var-appr-025a", "dual-2", "security", "approve", "2026-07-20T11:57:00Z", "2026-07-20T12:05:00Z", "PAY-25"),
            make_approval(case, req, "var-appr-025b", "dual-2", "payments-owner", "approve", "2026-07-20T11:57:10Z", "2026-07-20T12:05:00Z", "PAY-25"),
            make_approval(case, req, "var-appr-025c", "sec-1", "security", "approve", "2026-07-20T11:57:20Z", "2026-07-20T12:05:00Z", "PAY-25"),
        ]
        case["calls"].append(make_call(case, req, ADMIN, ADMIN, "payments-write", "POST", "/payments/variant-25", "mesh-gateway", "var-nonce-25", "10.42.25.4", "2026-07-20T11:59:30Z", ["payments:*"], approvals=approvals))
    else:
        raise AssertionError(name)
    return case


@pytest.fixture(scope="session")
def built_binary(tmp_path_factory):
    assert SOURCE.exists(), "/app/workload_gate.go is missing"
    source_text = SOURCE.read_text()
    forbidden = ["os/exec", "exec.Command", "CommandContext", "syscall.Exec", "/tests", "reward.txt", "pytest", "python", "subprocess"]
    for token in forbidden:
        assert token not in source_text
    binary = tmp_path_factory.mktemp("bin") / "workload-gate"
    subprocess.run(["/usr/local/go/bin/gofmt", "-w", str(SOURCE)], check=True, cwd="/app", timeout=30)
    subprocess.run(["/usr/local/go/bin/go", "build", "-o", str(binary), str(SOURCE)], check=True, cwd="/app", timeout=60)
    return binary


def test_public_input_integrity():
    for rel, expected in PUBLIC_HASHES.items():
        path = TASK_FILE / rel
        assert path.exists(), rel
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected


def test_public_output_matches_reference_at_required_path(built_binary):
    input_dir = TASK_FILE / "input_data"
    output_dir = TASK_FILE / "output_data"
    output_dir.mkdir(exist_ok=True)
    sentinel = output_dir / "keep.txt"
    sentinel.write_text("preserve me\n")
    for name in ("workload_decisions.jsonl", "workload_summary.json"):
        path = output_dir / name
        if path.exists():
            path.unlink()
    rows, summary = run_gate(built_binary, input_dir, output_dir)
    expected_rows, expected_summary = solve_case(input_dir)
    assert sentinel.read_text() == "preserve me\n"
    validate_output_schema(rows, summary)
    assert rows == expected_rows
    assert summary == expected_summary


@pytest.mark.parametrize("variant_name", VARIANTS)
def test_generated_variant_matches_reference(built_binary, tmp_path, variant_name):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    write_case(variant_case(variant_name), input_dir)
    rows, summary = run_gate(built_binary, input_dir, output_dir)
    expected_rows, expected_summary = solve_case(input_dir)
    validate_output_schema(rows, summary)
    assert rows == expected_rows
    assert summary == expected_summary


def test_hardcoded_public_reports_do_not_satisfy_variants(built_binary, tmp_path):
    public_rows, public_summary = solve_case(TASK_FILE / "input_data")
    mismatches = 0
    for variant_name in VARIANTS[:5]:
        input_dir = tmp_path / variant_name / "input"
        write_case(variant_case(variant_name), input_dir)
        expected_rows, expected_summary = solve_case(input_dir)
        if expected_rows != public_rows or expected_summary != public_summary:
            mismatches += 1
    assert mismatches == 5


def test_empty_output_directory_is_not_accepted(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert not (empty / "workload_decisions.jsonl").exists()
    assert not (empty / "workload_summary.json").exists()
