#!/usr/bin/env bash
set -euo pipefail

REGOLIB=/app/opalib
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

cat >"$TMP/input.json" <<'JSON'
{
  "events": [
    {
      "schema_version": 2,
      "event_id": "smoke-ex-win",
      "collector_id": "collector-east",
      "collector_sequence": 1,
      "observed_at": "2025-01-01T00:00:01Z",
      "tenant_id": "tenant-a",
      "trace_id": "tr-smoke-lose",
      "request_id": "req-smoke-1",
      "event_type": "token_issued",
      "payload": {"exchange_id": "ex-smoke-alpha"}
    },
    {
      "schema_version": 2,
      "event_id": "smoke-scope-nested",
      "collector_id": "collector-east",
      "collector_sequence": 2,
      "observed_at": "2025-01-01T00:00:02Z",
      "tenant_id": "tenant-a",
      "trace_id": "tr-scope",
      "request_id": "req-smoke-2",
      "event_type": "scope_decision",
      "payload": {
        "decision": "allow",
        "required": {"resource_scope": "vault:tenant-b:read"},
        "granted": {"scopes": ["vault:tenant-b:read"]},
        "resource_tenant": "tenant-b"
      }
    },
    {
      "schema_version": 2,
      "event_id": "smoke-fwd-missing-proxy",
      "collector_id": "collector-east",
      "collector_sequence": 3,
      "observed_at": "2025-01-01T00:00:03Z",
      "tenant_id": "tenant-a",
      "trace_id": "tr-fwd-miss",
      "request_id": "req-smoke-3",
      "event_type": "token_forwarded",
      "payload": {}
    },
    {
      "schema_version": 2,
      "event_id": "smoke-fwd-attempted",
      "collector_id": "collector-east",
      "collector_sequence": 4,
      "observed_at": "2025-01-01T00:00:04Z",
      "tenant_id": "tenant-a",
      "trace_id": "tr-fwd-att",
      "request_id": "req-smoke-4",
      "event_type": "token_forward_attempted",
      "payload": {"proxy_id": "proxy-untrusted-1"}
    },
    {
      "schema_version": 2,
      "event_id": "smoke-egress-blocked",
      "collector_id": "collector-east",
      "collector_sequence": 5,
      "observed_at": "2025-01-01T00:00:05Z",
      "tenant_id": "tenant-a",
      "trace_id": "tr-egress",
      "request_id": "req-smoke-5",
      "event_type": "egress_blocked",
      "payload": {"proxy_id": "proxy-untrusted-1"}
    },
    {
      "schema_version": 2,
      "event_id": "smoke-fwd-untrusted",
      "collector_id": "collector-east",
      "collector_sequence": 6,
      "observed_at": "2025-01-01T00:00:06Z",
      "tenant_id": "tenant-a",
      "trace_id": "tr-fwd-ok",
      "request_id": "req-smoke-6",
      "event_type": "token_forwarded",
      "payload": {
        "proxy_id": "proxy-untrusted-1",
        "token_fingerprint": "fp_visible_forward_01"
      }
    },
    {
      "schema_version": 2,
      "event_id": "smoke-revoke-visible",
      "collector_id": "collector-east",
      "collector_sequence": 8,
      "observed_at": "2025-01-01T00:00:08Z",
      "tenant_id": "tenant-a",
      "trace_id": "tr-visible-redact",
      "request_id": "req-visible-redact",
      "event_type": "token_revoked",
      "payload": {
        "token_fingerprint": "fp_visible_revoke_01",
        "effective_at": "2025-01-01T00:00:20Z"
      }
    },
    {
      "schema_version": 2,
      "event_id": "smoke-use-visible",
      "collector_id": "collector-east",
      "collector_sequence": 9,
      "observed_at": "2025-01-01T00:00:10Z",
      "tenant_id": "tenant-a",
      "trace_id": "tr-visible-redact",
      "request_id": "req-visible-redact",
      "event_type": "token_used",
      "payload": {
        "token_fingerprint": "fp_visible_revoke_01"
      }
    },
    {
      "schema_version": 2,
      "event_id": "smoke-no-payload-obj",
      "collector_id": "collector-east",
      "collector_sequence": 7,
      "observed_at": "2025-01-01T00:00:07Z",
      "tenant_id": "tenant-a",
      "trace_id": null,
      "request_id": "req-smoke-7",
      "event_type": "token_used",
      "payload": null
    }
  ],
  "trust_boundaries": {
    "untrusted_proxies": ["proxy-untrusted-1"],
    "trusted_proxies": ["proxy-internal-mesh"]
  }
}
JSON

opa check "$REGOLIB"
OUT=$(opa eval -d "$REGOLIB" -i "$TMP/input.json" 'data.tokenexposure.analysis')
echo "$OUT" | grep -q '"bearer_forwarding"' || {
  echo "expected bearer_forwarding finding in smoke output" >&2
  exit 1
}
echo "$OUT" | grep -q 'smoke-fwd-untrusted' || {
  echo "expected untrusted forward event in findings" >&2
  exit 1
}
echo "$OUT" | grep -q 'smoke-fwd-missing-proxy' && {
  echo "missing-proxy event must not appear in exposure findings" >&2
  exit 1
}
echo "$OUT" | grep -q 'smoke-fwd-attempted' || {
  echo "expected attempted forward in rejected candidates" >&2
  exit 1
}
echo "$OUT" | grep -q 'smoke-egress-blocked' || {
  echo "expected egress blocked in rejected candidates" >&2
  exit 1
}
echo "$OUT" | grep -qi 'eval_error' && {
  echo "opa eval returned an error" >&2
  exit 1
}
echo "$OUT" | grep -q 'fp_visible_forward_01' && {
  echo "raw forwarding token fingerprint leaked in OPA output" >&2
  exit 1
}
echo "$OUT" | grep -q 'fp_visible_revoke_01' && {
  echo "raw revocation token fingerprint leaked in OPA output" >&2
  exit 1
}
echo "$OUT" | grep -q 'tok_fp_visib' || {
  echo "expected visible redacted token label tok_fp_visib" >&2
  exit 1
}
echo policy-smoke-ok
