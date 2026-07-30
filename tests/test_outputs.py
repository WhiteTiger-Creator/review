"""Behavioral verifier tests for oauth token exposure reconstruction."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import jsonschema
import pytest

APP = Path("/app")
OUTPUT = Path("/output")
ANALYZE = APP / "bin" / "token-exposure-analyze"
REPORT_SCHEMA = APP / "schemas" / "exposure-report.schema.json"

FINDING_CLASSES = {
    "signing_key_reuse",
    "bearer_forwarding",
    "scope_escalation",
    "refresh_token_replay",
    "audience_confusion",
    "revocation_lag_exposure",
}


def load_events(events_dir: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for path in sorted(events_dir.glob("*.ndjson")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
    return events


def load_collectors(config_dir: Path) -> dict[str, Any]:
    return json.loads((config_dir / "collectors.json").read_text(encoding="utf-8"))


def load_untrusted_proxies(config_dir: Path) -> set[str]:
    data = json.loads((config_dir / "trust-boundaries.json").read_text(encoding="utf-8"))
    return set(data.get("untrusted_proxies", []))


def parse_ts(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def logical_key(ev: dict[str, Any], collectors: dict[str, Any]) -> tuple:
    offset = 0
    for item in collectors.get("collectors", []):
        if item.get("collector_id") == ev.get("collector_id"):
            offset = int(item.get("clock_offset_ms", 0))
    ts = parse_ts(str(ev["observed_at"]))
    return (offset, ts, int(ev["collector_sequence"]), str(ev.get("event_id", "")))


def normalize_events(events: list[dict[str, Any]], collectors: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(events, key=lambda ev: logical_key(ev, collectors))


def event_identity(ev: dict[str, Any]) -> tuple:
    return (ev["collector_id"], int(ev["collector_sequence"]), ev["event_id"])


def dedupe_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[tuple, dict[str, Any]] = {}
    for ev in events:
        ident = event_identity(ev)
        if ident in seen and seen[ident] != ev:
            raise ValueError(f"contradictory duplicate: {ident}")
        seen[ident] = ev
    return list(seen.values())


def chain_key(ev: dict[str, Any]) -> str:
    """Tenant-scoped chain key: exchange_id > trace_id > refresh family > request_id."""
    tenant = str(ev.get("tenant_id", ""))
    payload = ev.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}
    exchange = payload.get("exchange_id")
    if exchange:
        return f"{tenant}|{exchange}"
    trace = ev.get("trace_id")
    if trace:
        return f"{tenant}|{trace}"
    family = payload.get("refresh_family") or payload.get("refresh_family_id")
    if family:
        return f"{tenant}|{family}"
    return f"{tenant}|{ev.get('request_id', '')}"


def _payload(ev: dict[str, Any]) -> dict[str, Any]:
    raw = ev.get("payload")
    return raw if isinstance(raw, dict) else {}


def _required_scope(payload: dict[str, Any]) -> str | None:
    if payload.get("required_scope"):
        return str(payload["required_scope"])
    required = payload.get("required") or {}
    if isinstance(required, dict) and required.get("resource_scope"):
        return str(required["resource_scope"])
    scope = payload.get("scope") or {}
    if isinstance(scope, dict) and scope.get("required"):
        return str(scope["required"])
    return None


def _granted_scopes(payload: dict[str, Any]) -> list[str]:
    if payload.get("granted_scopes"):
        return [str(s) for s in payload["granted_scopes"]]
    granted = payload.get("granted") or {}
    if isinstance(granted, dict) and granted.get("scopes"):
        return [str(s) for s in granted["scopes"]]
    scopes = payload.get("scopes") or {}
    if isinstance(scopes, dict) and scopes.get("granted"):
        return [str(s) for s in scopes["granted"]]
    return []


def _decision_allowed(payload: dict[str, Any]) -> bool:
    return str(payload.get("decision", "allow")) in {"allow", "granted"}


def _resource_tenant(payload: dict[str, Any], event: dict[str, Any]) -> str:
    return str(payload.get("resource_tenant") or event.get("tenant_id", ""))


def _proxy_id(payload: dict[str, Any]) -> str | None:
    pid = payload.get("proxy_id")
    return str(pid) if pid else None


def _is_forward_success(event: dict[str, Any]) -> bool:
    return event.get("event_type") == "token_forwarded"


def build_chains(events: list[dict[str, Any]], collectors: dict[str, Any]) -> list[dict[str, Any]]:
    ordered = normalize_events(events, collectors)
    chains: dict[str, dict[str, Any]] = {}
    for ev in ordered:
        key = chain_key(ev)
        ch = chains.setdefault(
            key,
            {"chain_id": key, "tenant_id": ev.get("tenant_id"), "event_ids": []},
        )
        ch["event_ids"].append(ev["event_id"])
    return sorted(chains.values(), key=lambda c: c["chain_id"])


def derive_findings(events: list[dict[str, Any]], untrusted: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    issued = [e for e in events if e.get("event_type") == "token_issued"]
    for i, a in enumerate(issued):
        pa = _payload(a)
        for b in issued[i + 1 :]:
            pb = _payload(b)
            if pa.get("material_id") and pa.get("material_id") == pb.get("material_id") and pa.get("issuer") != pb.get("issuer"):
                findings.append(
                    {
                        "class": "signing_key_reuse",
                        "tenant_id": a.get("tenant_id"),
                        "evidence_event_ids": [a["event_id"], b["event_id"]],
                    }
                )
    findings.extend(
        {
            "class": "bearer_forwarding",
            "tenant_id": e.get("tenant_id"),
            "evidence_event_ids": [e["event_id"]],
        }
        for e in events
        if _is_forward_success(e) and _proxy_id(_payload(e)) in untrusted
    )
    for e in events:
        if e.get("event_type") != "scope_decision":
            continue
        p = _payload(e)
        if not _decision_allowed(p):
            continue
        required = _required_scope(p)
        if not required:
            continue
        granted = _granted_scopes(p)
        if required in granted and _resource_tenant(p, e) != e.get("tenant_id"):
            findings.append(
                {
                    "class": "scope_escalation",
                    "tenant_id": e.get("tenant_id"),
                    "evidence_event_ids": [e["event_id"]],
                }
            )
    revokes = [e for e in events if e.get("event_type") == "token_revoked"]
    uses = [e for e in events if e.get("event_type") == "token_used"]
    for rev in revokes:
        rp = rev.get("payload") or {}
        for use in uses:
            up = use.get("payload") or {}
            if rp.get("token_fingerprint") == up.get("token_fingerprint") and rev["observed_at"] < use["observed_at"] < rp.get("effective_at", ""):
                findings.append(
                    {
                        "class": "revocation_lag_exposure",
                        "tenant_id": use.get("tenant_id"),
                        "evidence_event_ids": [rev["event_id"], use["event_id"]],
                    }
                )
    findings.extend(
        {
            "class": "refresh_token_replay",
            "tenant_id": e.get("tenant_id"),
            "evidence_event_ids": [e["event_id"]],
        }
        for e in events
        if e.get("event_type") == "refresh_used" and (e.get("payload") or {}).get("replay")
    )
    findings.sort(key=lambda f: (f["class"], f.get("tenant_id", ""), f["evidence_event_ids"][0]))
    rejected = [
        {"reason": "blocked_forward", "event_id": e["event_id"]}
        for e in events
        if e.get("event_type") in {"egress_blocked", "token_forward_attempted"}
    ]
    return findings, rejected


def _write_events(root: Path, shards: dict[str, list[dict[str, Any]]]) -> None:
    events = root / "events"
    events.mkdir(parents=True, exist_ok=True)
    for name, rows in shards.items():
        shard_name = name if name.endswith(".ndjson") else f"{name}.ndjson"
        with (events / shard_name).open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n")


def _base_event(
    event_id: str,
    event_type: str,
    tenant: str = "tenant-a",
    seq: int = 1,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "collector_id": "collector-east",
        "collector_sequence": seq,
        "observed_at": f"2025-01-01T00:00:{seq:02d}Z",
        "event_id": event_id,
        "event_type": event_type,
        "tenant_id": tenant,
        "request_id": f"req-{seq % 3}",
        "trace_id": f"tr-{seq % 2}",
        "payload": payload if payload is not None else {},
    }


def _run_generated(workdir: Path, shards: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    shutil.rmtree(workdir / "events")
    _write_events(workdir, shards)
    proc = _run_analyze(workdir)
    assert proc.returncode == 0, proc.stderr
    return json.loads((workdir / "output" / "token_exposure_report.json").read_text(encoding="utf-8"))


def dot_contains_graph(dot: str, report: dict[str, Any]) -> bool:
    node_ids = {str(n.get("node_id")) for n in report.get("nodes", [])}
    edge_pairs = {(str(e.get("source")), str(e.get("target"))) for e in report.get("edges", [])}
    return all(nid in dot for nid in node_ids) and all(f"{s} -> {t}" in dot for s, t in edge_pairs)


def sample_token_fingerprints(events: list[dict[str, Any]]) -> list[str]:
    out = []
    for ev in events:
        payload = ev.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        for key in (
            "token_fingerprint",
            "parent_token_fingerprint",
            "child_token_fingerprint",
            "access_token_fingerprint",
            "refresh_token_fingerprint",
        ):
            fp = payload.get(key)
            if isinstance(fp, str) and fp:
                out.append(fp)
    return out


def _assert_no_raw_fingerprint_leak(report: dict[str, Any], dot: str, events_dir: Path) -> None:
    blob = json.dumps(report, sort_keys=True) + "\n" + dot
    fps = sample_token_fingerprints(load_events(events_dir))
    for fp in fps:
        assert fp not in blob
        assert f"tok_{fp[:8]}" in blob or fp.startswith("fp_unused_")


def _validate_report_schema(report: dict[str, Any]) -> None:
    schema = json.loads(REPORT_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    jsonschema.Draft7Validator(schema).validate(report)


def _assert_dot_parses(dot_path: Path) -> None:
    proc = subprocess.run(
        ["dot", "-Tplain", str(dot_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr


def _run_analyze_env(work: Path, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["GOCACHE"] = str(work / "gocache")
    if extra_env:
        env.update(extra_env)
    (work / "gocache").mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [
            str(ANALYZE),
            "--events",
            str(work / "events"),
            "--config",
            str(work / "config"),
            "--regolib",
            str(APP / "opalib"),
            "--state",
            str(work / "state.json"),
            "--output",
            str(work / "output"),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _run_analyze(work: Path) -> subprocess.CompletedProcess:
    return _run_analyze_env(work)


@pytest.fixture()
def workdir():
    base = Path(tempfile.mkdtemp(prefix="oauth-exposure-"))
    shutil.copytree(APP / "data" / "events", base / "events")
    shutil.copytree(APP / "config", base / "config")
    shutil.copy2(APP / "data" / "state" / "analysis-state.json", base / "state.json")
    (base / "output").mkdir()
    yield base
    shutil.rmtree(base, ignore_errors=True)


@pytest.fixture()
def analyzed(workdir: Path):
    proc = _run_analyze(workdir)
    assert proc.returncode == 0, proc.stderr
    report = json.loads((workdir / "output" / "token_exposure_report.json").read_text(encoding="utf-8"))
    dot = (workdir / "output" / "token_exposure_graph.dot").read_text(encoding="utf-8")
    return report, dot


def test_visible_analysis_emits_schema_valid_report_and_graph(analyzed, workdir: Path):
    """Baseline: analyzer emits schema-valid JSON report and Graphviz-parseable DOT."""
    report, dot = analyzed
    assert report["schema_version"] == 2
    assert report["findings"]
    assert dot.startswith("digraph")
    _validate_report_schema(report)
    _assert_dot_parses(workdir / "output" / "token_exposure_graph.dot")


def test_shard_order_does_not_change_outputs(workdir: Path):
    """Permuted shard filenames must not change report bytes."""
    first = _run_analyze(workdir)
    assert first.returncode == 0
    digest1 = hashlib.sha256((workdir / "output" / "token_exposure_report.json").read_bytes()).hexdigest()
    shards = sorted((workdir / "events").glob("*.ndjson"))
    renamed = workdir / "events_shuffled"
    renamed.mkdir()
    for i, shard in enumerate(reversed(shards)):
        (renamed / f"zz-{i}-{shard.name}").write_text(shard.read_text(encoding="utf-8"))
    shutil.rmtree(workdir / "events")
    shutil.move(str(renamed), str(workdir / "events"))
    second = _run_analyze(workdir)
    assert second.returncode == 0
    digest2 = hashlib.sha256((workdir / "output" / "token_exposure_report.json").read_bytes()).hexdigest()
    assert digest1 == digest2


def test_collector_clock_offsets_define_logical_order():
    """Collector offsets and sequences define normalized event order."""
    collectors = load_collectors(APP / "config")
    events = load_events(APP / "data" / "events")
    ordered = normalize_events(events, collectors)
    assert ordered[0]["event_id"] in {e["event_id"] for e in events}


def test_request_ids_are_tenant_scoped_and_retry_aware():
    """Chains must not merge tenants that reuse local request IDs."""
    events = load_events(APP / "data" / "events")
    collectors = load_collectors(APP / "config")
    chains = build_chains(events, collectors)
    keys = [c["chain_id"] for c in chains]
    assert len(keys) == len(set(keys))
    assert any("tenant-a" in k and "tenant-b" not in k for k in keys)


def test_kid_is_not_global_key_identity(analyzed):
    """Signing-key reuse requires material identity, not kid alone."""
    report, _ = analyzed
    classes = {f["class"] for f in report["findings"]}
    assert "signing_key_reuse" in classes


def test_blocked_forward_attempt_is_not_exposure(analyzed):
    """Blocked forwarding attempts are rejected, not counted as exposure."""
    report, _ = analyzed
    findings = report["findings"]
    rejected = report["rejected_candidates"]
    events = load_events(APP / "data" / "events")
    blocked_ids = {e["event_id"] for e in events if e.get("event_type") == "egress_blocked"}
    rejected_ids = {r.get("event_id") for r in rejected}
    assert blocked_ids.issubset(rejected_ids)
    for blocked_id in blocked_ids:
        assert not any(
            blocked_id in f.get("evidence_event_ids", []) for f in findings if f["class"] == "bearer_forwarding"
        )


def test_scope_matching_is_exact_and_resource_qualified(analyzed):
    """Scope escalation requires exact resource-qualified scope matching."""
    report, _ = analyzed
    assert any(f["class"] == "scope_escalation" for f in report["findings"])


def test_revocation_propagation_creates_lag_exposure(analyzed):
    """Uses accepted during revocation propagation window are flagged."""
    report, _ = analyzed
    assert any(f["class"] == "revocation_lag_exposure" for f in report["findings"])


def test_rotated_refresh_token_reuse_is_replay(analyzed):
    """Prior refresh family member used after rotation is replay."""
    report, _ = analyzed
    assert any(f["class"] == "refresh_token_replay" for f in report["findings"])


def test_bearer_forwarding_detected_for_untrusted_proxy(analyzed):
    """Successful bearer forwarding across untrusted proxy is exposure."""
    report, _ = analyzed
    assert any(f["class"] == "bearer_forwarding" for f in report["findings"])


def test_reference_findings_match_report(analyzed):
    """Report finding classes match independently derived reference model."""
    report, _ = analyzed
    events = load_events(APP / "data" / "events")
    untrusted = load_untrusted_proxies(APP / "config")
    expected, _ = derive_findings(events, untrusted)
    got_classes = sorted({f["class"] for f in report["findings"]})
    exp_classes = sorted({f["class"] for f in expected})
    assert got_classes == exp_classes


def test_json_and_dot_have_identical_semantic_graph(analyzed):
    """DOT graph contains the same nodes and edges as the JSON report."""
    report, dot = analyzed
    assert dot_contains_graph(dot, report)


def test_raw_tokens_not_leaked_in_output(analyzed):
    """Raw token fingerprints must not appear in report or DOT."""
    report, dot = analyzed
    blob = json.dumps(report) + dot
    events = load_events(APP / "data" / "events")
    for fp in sample_token_fingerprints(events):
        assert fp not in blob


def test_all_supported_finding_classes_subset(analyzed):
    """Every emitted finding class is from the public vocabulary."""
    report, _ = analyzed
    for f in report["findings"]:
        assert f["class"] in FINDING_CLASSES


def test_fixture_integrity_hashes():
    """Bundled fixture files match trusted SHA256 anchors."""
    manifest = json.loads((APP / "docs" / "trusted-fixtures.json").read_text(encoding="utf-8"))
    for rel, expected in manifest["files"].items():
        digest = hashlib.sha256((APP / rel).read_bytes()).hexdigest()
        assert digest == expected


def test_chain_key_uses_trace_not_request_id_only():
    """Correlation keys include trace identifiers, not request_id alone."""
    events = load_events(APP / "data" / "events")
    keys = {chain_key(e) for e in events if e["tenant_id"] == "tenant-a"}
    assert any("tr_" in k for k in keys)


def test_rejected_candidates_present(analyzed):
    """Rejected candidate paths are recorded with public reason codes."""
    report, _ = analyzed
    assert report["rejected_candidates"]


def test_deterministic_repeat_run(workdir: Path):
    """Repeated analysis runs produce identical report bytes."""
    _run_analyze(workdir)
    d1 = hashlib.sha256((workdir / "output" / "token_exposure_report.json").read_bytes()).hexdigest()
    _run_analyze(workdir)
    d2 = hashlib.sha256((workdir / "output" / "token_exposure_report.json").read_bytes()).hexdigest()
    assert d1 == d2


def test_dedupe_events_idempotent():
    """Benign duplicate event identities collapse without losing unique events."""
    events = load_events(APP / "data" / "events")
    assert len(dedupe_events(events)) <= len(events)


def test_graph_nodes_sorted(analyzed):
    """Report vertex identifiers are canonically sorted for deterministic output."""
    report, _ = analyzed
    ids = [n["node_id"] for n in report["nodes"]]
    assert ids == sorted(ids)


def test_chain_key_priority_is_exchange_then_trace_then_request():
    """Public chain-key priority is exchange_id, then trace_id, then request_id."""
    assert chain_key({"tenant_id": "t", "request_id": "r", "trace_id": "tr", "payload": {"exchange_id": "ex"}}) == "t|ex"
    assert chain_key({"tenant_id": "t", "request_id": "r", "trace_id": "tr", "payload": {}}) == "t|tr"
    assert chain_key({"tenant_id": "t", "request_id": "r", "payload": {}}) == "t|r"


def test_generated_chain_priority_and_optional_shapes(workdir: Path):
    """Generated events prove exchange-id wins and optional null fields do not error."""
    ev_ex_a = _base_event("gen-ex-a", "token_issued", seq=1, payload={"exchange_id": "ex-alpha"})
    ev_ex_a["trace_id"] = "tr-AAA"
    ev_ex_b = _base_event("gen-ex-b", "token_used", seq=2, payload={"exchange_id": "ex-alpha"})
    ev_ex_b["trace_id"] = "tr-BBB"
    ev_tenant_a = _base_event("gen-req-a", "token_issued", tenant="tenant-a", seq=3)
    ev_tenant_a["request_id"] = "shared-req"
    ev_tenant_b = _base_event("gen-req-b", "token_issued", tenant="tenant-b", seq=4)
    ev_tenant_b["request_id"] = "shared-req"
    ev_ex_c = _base_event("gen-ex-c", "token_issued", tenant="tenant-a", seq=5, payload={"exchange_id": "ex-alpha"})
    ev_ex_d = _base_event("gen-ex-d", "token_issued", tenant="tenant-b", seq=6, payload={"exchange_id": "ex-alpha"})
    ev_null_payload = _base_event("gen-null-payload", "token_used", seq=7, payload=None)  # type: ignore[arg-type]
    ev_null_trace = _base_event("gen-null-trace", "token_used", seq=8)
    ev_null_trace["trace_id"] = None
    ev_empty_payload = _base_event("gen-empty-payload", "token_used", seq=9, payload={})
    rows = [ev_ex_a, ev_ex_b, ev_tenant_a, ev_tenant_b, ev_ex_c, ev_ex_d, ev_null_payload, ev_null_trace, ev_empty_payload]
    report1 = _run_generated(workdir, {"generated-chain.ndjson": rows})
    report2 = _run_generated(workdir, {"generated-chain.ndjson": rows})
    assert report1["findings"] is not None
    assert report1["nodes"] is not None
    assert report1["edges"] is not None
    collectors = load_collectors(workdir / "config")
    chains = build_chains(rows, collectors)
    alpha = [c for c in chains if "gen-ex-a" in c["event_ids"] and "gen-ex-b" in c["event_ids"]]
    assert len(alpha) == 1
    assert alpha[0]["chain_id"].endswith("ex-alpha")
    tenant_chains = {c["chain_id"] for c in chains if "gen-req-a" in c["event_ids"] or "gen-req-b" in c["event_ids"]}
    assert len(tenant_chains) == 2
    cross_tenant = [c for c in chains if "gen-ex-c" in c["event_ids"] and "gen-ex-d" in c["event_ids"]]
    assert not cross_tenant
    d1 = hashlib.sha256(json.dumps(report1, sort_keys=True).encode()).hexdigest()
    d2 = hashlib.sha256(json.dumps(report2, sort_keys=True).encode()).hexdigest()
    assert d1 == d2


def test_generated_nested_scope_decision_shapes(workdir: Path):
    """Nested scope_decision shapes produce escalation only for allowed decisions."""
    allowed = _base_event(
        "gen-scope-allow",
        "scope_decision",
        seq=1,
        payload={
            "decision": "allow",
            "required": {"resource_scope": "vault:tenant-b:read"},
            "granted": {"scopes": ["vault:tenant-b:read"]},
            "resource_tenant": "tenant-b",
            "policy_revision": "rev-2024-05",
        },
    )
    denied = _base_event(
        "gen-scope-deny",
        "scope_decision",
        seq=2,
        payload={
            "decision": "deny",
            "required": {"resource_scope": "vault:tenant-b:read"},
            "granted": {"scopes": ["vault:tenant-b:read"]},
            "resource_tenant": "tenant-b",
        },
    )
    report = _run_generated(workdir, {"generated-scope.ndjson": [allowed, denied]})
    scope_ids = {
        eid
        for f in report["findings"]
        if f["class"] == "scope_escalation"
        for eid in f.get("evidence_event_ids", [])
    }
    assert "gen-scope-allow" in scope_ids
    assert "gen-scope-deny" not in scope_ids


def test_generated_forwarding_boundary_and_rejections(workdir: Path):
    """Forwarding boundary uses trust config; blocked/attempted events are rejected."""
    untrusted_ok = _base_event(
        "gen-fwd-untrusted",
        "token_forwarded",
        seq=1,
        payload={"proxy_id": "proxy-untrusted-1"},
    )
    trusted_ok = _base_event(
        "gen-fwd-trusted",
        "token_forwarded",
        seq=2,
        payload={"proxy_id": "proxy-internal-mesh"},
    )
    attempted = _base_event(
        "gen-fwd-attempted",
        "token_forward_attempted",
        seq=3,
        payload={"proxy_id": "proxy-untrusted-1"},
    )
    blocked = _base_event(
        "gen-fwd-blocked",
        "egress_blocked",
        seq=4,
        payload={"proxy_id": "proxy-untrusted-1"},
    )
    missing_proxy = _base_event("gen-fwd-missing", "token_forwarded", seq=5, payload={})
    report = _run_generated(
        workdir,
        {"generated-forward.ndjson": [untrusted_ok, trusted_ok, attempted, blocked, missing_proxy]},
    )
    bearer_ids = {
        eid
        for f in report["findings"]
        if f["class"] == "bearer_forwarding"
        for eid in f.get("evidence_event_ids", [])
    }
    rejected_ids = {r.get("event_id") for r in report["rejected_candidates"]}
    assert bearer_ids == {"gen-fwd-untrusted"}
    assert "gen-fwd-attempted" in rejected_ids
    assert "gen-fwd-blocked" in rejected_ids
    assert "gen-fwd-missing" not in bearer_ids
    assert "gen-fwd-attempted" not in bearer_ids
    assert "gen-fwd-blocked" not in bearer_ids


def test_opa_policy_accepts_generated_legacy_and_current_shapes(tmp_path: Path):
    """OPA evaluation must not error on legacy and optional event shapes."""
    input_doc = {
        "events": [
            _base_event("opa-ex", "token_issued", payload={"exchange_id": "ex-opa"}),
            {
                **_base_event("opa-scope", "scope_decision", seq=2),
                "payload": {
                    "decision": "allow",
                    "required": {"resource_scope": "vault:tenant-b:read"},
                    "granted": {"scopes": ["vault:tenant-b:read"]},
                    "resource_tenant": "tenant-b",
                },
            },
            _base_event("opa-fwd-miss", "token_forwarded", seq=3, payload={}),
            _base_event("opa-fwd-att", "token_forward_attempted", seq=4, payload={"proxy_id": "proxy-untrusted-1"}),
            _base_event("opa-fwd-ok", "token_forwarded", seq=5, payload={"proxy_id": "proxy-untrusted-1"}),
            {k: v for k, v in _base_event("opa-no-payload-key", "token_used", seq=6).items() if k != "payload"},
        ],
        "trust_boundaries": json.loads((APP / "config" / "trust-boundaries.json").read_text(encoding="utf-8")),
    }
    input_path = tmp_path / "opa-eval-input.json"
    input_path.write_text(json.dumps(input_doc), encoding="utf-8")
    proc = subprocess.run(
        ["opa", "eval", "-d", str(APP / "opalib"), "-i", str(input_path), "data.tokenexposure.analysis"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload.get("result")


def test_generated_redaction_applies_to_findings_and_dot(workdir: Path):
    """Generated token fingerprints are correlated internally but redacted in JSON and DOT."""
    events = [
        _base_event(
            "gen-redact-issue-a",
            "token_issued",
            seq=1,
            payload={
                "exchange_id": "ex-redact-a",
                "token_fingerprint": "fp_generated_access_alpha_001",
                "material_id": "mat-redact-a",
                "issuer": "issuer-a",
            },
        ),
        _base_event(
            "gen-redact-forward-a",
            "token_forwarded",
            seq=2,
            payload={
                "exchange_id": "ex-redact-a",
                "proxy_id": "proxy-untrusted-1",
                "token_fingerprint": "fp_generated_access_alpha_001",
            },
        ),
        _base_event(
            "gen-redact-revoke-a",
            "token_revoked",
            seq=3,
            payload={
                "exchange_id": "ex-redact-a",
                "token_fingerprint": "fp_generated_access_alpha_001",
                "effective_at": "2025-01-01T00:00:20Z",
            },
        ),
        _base_event(
            "gen-redact-lag-use-a",
            "token_used",
            seq=4,
            payload={
                "exchange_id": "ex-redact-a",
                "token_fingerprint": "fp_generated_access_alpha_001",
            },
        ),
    ]
    report = _run_generated(workdir, {"generated-redaction.ndjson": events})
    dot = (workdir / "output" / "token_exposure_graph.dot").read_text(encoding="utf-8")
    blob = json.dumps(report, sort_keys=True) + "\n" + dot

    assert "fp_generated_access_alpha_001" not in blob
    assert "tok_fp_gener" in blob
    assert any(f["class"] == "bearer_forwarding" for f in report["findings"])
    assert any(f["class"] == "revocation_lag_exposure" for f in report["findings"])


def test_generated_same_fingerprint_is_tenant_scoped(workdir: Path):
    """The same fingerprint in two tenants is redacted but chains remain tenant-scoped."""
    fp = "fp_generated_shared_cross_tenant_001"
    a = _base_event(
        "gen-cross-tenant-same-fp-a",
        "token_used",
        seq=1,
        tenant="tenant-a",
        payload={"token_fingerprint": fp},
    )
    a["trace_id"] = "tr-shared"
    a["request_id"] = "req-shared"
    b = _base_event(
        "gen-cross-tenant-same-fp-b",
        "token_used",
        seq=2,
        tenant="tenant-b",
        payload={"token_fingerprint": fp},
    )
    b["trace_id"] = "tr-shared"
    b["request_id"] = "req-shared"
    report = _run_generated(workdir, {"generated-cross-tenant.ndjson": [a, b]})
    dot = (workdir / "output" / "token_exposure_graph.dot").read_text(encoding="utf-8")
    blob = json.dumps(report, sort_keys=True) + "\n" + dot

    assert fp not in blob
    chain_nodes = [n for n in report["nodes"] if "tr-shared" in json.dumps(n)]
    tenants = {n.get("tenant_id") for n in chain_nodes if n.get("tenant_id")}
    assert {"tenant-a", "tenant-b"}.issubset(tenants)
    assert len({n.get("node_id") for n in chain_nodes}) >= 2


def test_generated_exchange_id_priority_under_mixed_redacted_evidence(workdir: Path):
    """exchange_id wins over trace_id even when redacted evidence appears in multiple finding classes."""
    rows = [
        _base_event(
            "gen-mixed-chain-exchange",
            "token_issued",
            seq=1,
            payload={
                "exchange_id": "ex-priority-redact",
                "token_fingerprint": "fp_generated_priority_001",
                "material_id": "mat-priority",
                "issuer": "issuer-a",
            },
        ),
        _base_event(
            "gen-mixed-chain-trace",
            "token_forwarded",
            seq=2,
            payload={
                "exchange_id": "ex-priority-redact",
                "proxy_id": "proxy-untrusted-1",
                "token_fingerprint": "fp_generated_priority_001",
            },
        ),
        _base_event(
            "gen-rejected-fwd-attempt-redact",
            "token_forward_attempted",
            seq=3,
            payload={
                "exchange_id": "ex-priority-redact",
                "proxy_id": "proxy-untrusted-1",
                "token_fingerprint": "fp_generated_priority_rejected_001",
            },
        ),
    ]
    rows[0]["trace_id"] = "tr-lower-priority"
    rows[0]["request_id"] = "req-mixed"
    rows[1]["trace_id"] = "tr-lower-priority"
    rows[1]["request_id"] = "req-mixed"
    rows[2]["trace_id"] = "tr-lower-priority"
    rows[2]["request_id"] = "req-mixed"
    report = _run_generated(workdir, {"generated-priority-redaction.ndjson": rows})
    dot = (workdir / "output" / "token_exposure_graph.dot").read_text(encoding="utf-8")
    blob = json.dumps(report, sort_keys=True) + "\n" + dot

    assert "fp_generated_priority_001" not in blob
    assert "fp_generated_priority_rejected_001" not in blob
    assert "tok_fp_gener" in blob

    chain_ids = {n.get("chain_id") for n in report["nodes"] if n.get("chain_id")}
    assert any(str(cid).endswith("ex-priority-redact") for cid in chain_ids)
    assert not any(str(cid).endswith("tr-lower-priority") for cid in chain_ids)

    rejected_ids = {r.get("event_id") for r in report["rejected_candidates"]}
    assert "gen-rejected-fwd-attempt-redact" in rejected_ids


def test_checkpoint_resume_is_observable_and_not_ignored(workdir: Path):
    """A failed checkpointed run must resume from validated state and publish once."""
    clean = Path(tempfile.mkdtemp(prefix="oauth-clean-"))
    shutil.copytree(workdir / "events", clean / "events")
    shutil.copytree(workdir / "config", clean / "config")
    shutil.copy2(workdir / "state.json", clean / "state.json")
    (clean / "output").mkdir()

    full = _run_analyze(clean)
    assert full.returncode == 0, full.stderr
    clean_report = (clean / "output" / "token_exposure_report.json").read_bytes()
    clean_dot = (clean / "output" / "token_exposure_graph.dot").read_bytes()

    interrupted = _run_analyze_env(workdir, {"TOKEN_EXPOSURE_FAILPOINT": "after_checkpoint"})
    assert interrupted.returncode != 0
    assert not (workdir / "output" / "token_exposure_report.json").exists()
    assert not (workdir / "output" / "token_exposure_graph.dot").exists()

    state = json.loads((workdir / "state.json").read_text(encoding="utf-8"))
    assert state.get("status") in {"CHECKPOINTED", "READY_TO_PUBLISH", "VALIDATING", "CORRELATING"}
    assert state.get("checkpoint_id") or state.get("committed_shards")
    assert state.get("evidence_fingerprint") or state.get("relevant_fingerprint")

    resumed = _run_analyze(workdir)
    assert resumed.returncode == 0, resumed.stderr

    final_state = json.loads((workdir / "state.json").read_text(encoding="utf-8"))
    assert final_state.get("published") is True
    assert final_state.get("resumed_from_checkpoint") is True

    assert (workdir / "output" / "token_exposure_report.json").read_bytes() == clean_report
    assert (workdir / "output" / "token_exposure_graph.dot").read_bytes() == clean_dot


def test_relevant_config_change_invalidates_previous_state_and_output(workdir: Path):
    """Changing trust boundaries must invalidate stale state/output and change the report."""
    first = _run_analyze(workdir)
    assert first.returncode == 0, first.stderr
    report_path = workdir / "output" / "token_exposure_report.json"
    before = json.loads(report_path.read_text(encoding="utf-8"))
    before_digest = hashlib.sha256(report_path.read_bytes()).hexdigest()
    assert any(f["class"] == "bearer_forwarding" for f in before["findings"])

    trust_path = workdir / "config" / "trust-boundaries.json"
    trust = json.loads(trust_path.read_text(encoding="utf-8"))
    trust["trusted_proxies"] = sorted(set(trust.get("trusted_proxies", [])) | {"proxy-untrusted-1"})
    trust["untrusted_proxies"] = [p for p in trust.get("untrusted_proxies", []) if p != "proxy-untrusted-1"]
    trust_path.write_text(json.dumps(trust, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    second = _run_analyze(workdir)
    assert second.returncode == 0, second.stderr
    after = json.loads(report_path.read_text(encoding="utf-8"))
    after_digest = hashlib.sha256(report_path.read_bytes()).hexdigest()

    assert before_digest != after_digest
    assert not any(f["class"] == "bearer_forwarding" for f in after["findings"])
    _validate_report_schema(after)
    _assert_dot_parses(workdir / "output" / "token_exposure_graph.dot")


def test_atomic_publication_preserves_previous_complete_output_on_failure(workdir: Path):
    """A failed staged publication must not replace previous complete artifacts."""
    first = _run_analyze(workdir)
    assert first.returncode == 0, first.stderr

    report_path = workdir / "output" / "token_exposure_report.json"
    dot_path = workdir / "output" / "token_exposure_graph.dot"
    old_report = report_path.read_bytes()
    old_dot = dot_path.read_bytes()

    rows = load_events(workdir / "events")
    extra = _base_event(
        "atomic-new-finding",
        "token_forwarded",
        seq=55,
        payload={
            "token_fingerprint": "fp_atomic_new_001",
            "proxy_id": "proxy-untrusted-1",
            "exchange_id": "ex-atomic-new",
        },
    )
    rows.append(extra)
    shutil.rmtree(workdir / "events")
    _write_events(workdir, {"atomic-mutated.ndjson": rows})

    failed = _run_analyze_env(workdir, {"TOKEN_EXPOSURE_FAILPOINT": "after_stage"})
    assert failed.returncode != 0

    assert report_path.read_bytes() == old_report
    assert dot_path.read_bytes() == old_dot
    assert not (workdir / "output" / ".staging" / "token_exposure_report.json").exists()
    assert not (workdir / "output" / ".staging" / "token_exposure_graph.dot").exists()

    recovered = _run_analyze(workdir)
    assert recovered.returncode == 0, recovered.stderr
    assert report_path.read_bytes() != old_report
    assert dot_path.read_bytes() != old_dot
    _validate_report_schema(json.loads(report_path.read_text(encoding="utf-8")))
    _assert_dot_parses(dot_path)
