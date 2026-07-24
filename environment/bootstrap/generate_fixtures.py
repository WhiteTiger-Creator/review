"""Generate GraphML, legacy YAML, dossier corpus, OIDC contracts, and canonical data."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

ROOT = Path(os.environ.get("TASK_ENV_ROOT", str(Path(__file__).resolve().parents[1])))
APP = Path(os.environ.get("APP_ROOT", str(ROOT / "environment")))
CANONICAL = Path(os.environ.get("CANONICAL_ROOT", str(ROOT / "canonical")))
OIDC = Path(os.environ.get("OIDC_CONTRACT_ROOT", str(ROOT / "oidc-contracts")))
AUTH = Path(os.environ.get("DOSSIER_AUTHORITY_ROOT", str(ROOT / "dossier-authority")))
DOSSIER = APP / "dossier"


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def checksums(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def install_graphml() -> None:
    template = Path(__file__).resolve().parent / "templates" / "service-callgraph.graphml"
    write(APP / "input" / "service-callgraph.graphml", template.read_text(encoding="utf-8"))


def legacy_yaml() -> str:
    return """global:
  audiences:
    - https://api.example.com
environments:
  production:
    audiences:
      - https://api.example.com/prod
  staging:
    audiences:
      - https://api.example.com/staging
services:
  user-service:
    audiences:
      - https://users.example.com
  billing-service:
    audiences:
      - https://billing.example.com
edges:
  - source: api-gateway
    target: auth-service
    environment: production
    method: POST
    path: /auth/validate
    audiences:
      - https://auth.example.com
  - source: api-gateway
    target: payment-service
    environment: production
    method: POST
    path: /payments/refund
    deny: true
"""


def oidc_revision_a() -> tuple[dict, dict]:
    disc = {
        "issuer": "https://accounts.google.com",
        "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs",
        "id_token_signing_alg_values_supported": ["RS256", "ES256", "HS256", "none"],
    }
    jwks = {
        "keys": [
            {"kid": "rsa-valid-1", "kty": "RSA", "alg": "RS256", "use": "sig", "key_ops": ["verify"]},
            {"kid": "ec-valid-1", "kty": "EC", "alg": "ES256", "use": "sig", "key_ops": ["verify"]},
            {"kid": "enc-only", "kty": "RSA", "alg": "RS256", "use": "enc"},
            {"kid": "hmac-bad", "kty": "oct", "alg": "HS256", "use": "sig"},
            {"kid": "no-ops", "kty": "RSA", "alg": "RS256", "use": "sig", "key_ops": ["encrypt"]},
        ]
    }
    return disc, jwks


def oidc_revision_b() -> tuple[dict, dict]:
    disc = {
        "issuer": "https://accounts.google.com",
        "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs-rotated",
        "id_token_signing_alg_values_supported": ["ES256", "RS256"],
    }
    jwks = {
        "keys": [
            {"kid": "ec-valid-2", "kty": "EC", "alg": "ES256", "use": "sig", "key_ops": ["verify"]},
            {"kid": "rsa-valid-2", "kty": "RSA", "use": "sig", "key_ops": ["verify"]},
            {"kid": "enc-only-b", "kty": "RSA", "alg": "RS256", "use": "enc"},
        ]
    }
    return disc, jwks


def dossier_files() -> list[tuple[str, str]]:
    files = [
        ("decision-register/DEC-001-accepted-edge-auth.yaml", """id: DEC-001
status: accepted
scope: edge
effective_date: 2025-06-01
source:
  service: api-gateway
  environment: production
  method: POST
  path: /auth/validate
target_service: auth-service
audiences:
  - https://auth.example.com/oauth2
algorithms:
  - RS256
"""),
        ("decision-register/DEC-002-superseded-audience.yaml", """id: DEC-002
status: superseded
scope: service
effective_date: 2025-09-01
target_service: user-service
audiences:
  - https://legacy-users.example.com
"""),
        ("decision-register/DEC-003-accepted-service-user.yaml", """id: DEC-003
status: accepted
scope: service
effective_date: 2025-03-15
target_service: user-service
audiences:
  - https://users.example.com/v2
"""),
        ("decision-register/DEC-004-amendment.yaml", """id: DEC-004
status: amended
scope: service
effective_date: 2025-07-01
amends: DEC-003
target_service: user-service
audiences:
  - https://users.example.com/v2/prod
"""),
        ("decision-register/DEC-005-staging-readonly.yaml", """id: DEC-005
status: accepted
scope: edge
effective_date: 2025-05-10
source:
  service: api-gateway
  environment: staging
  method: GET
  path: /users/profile
target_service: user-service
audiences:
  - https://api.example.com/staging/read
"""),
        ("decision-register/DEC-006-proposed.yaml", """id: DEC-006
status: proposed
scope: global
effective_date: 2025-10-01
issuer: https://evil.example.com
"""),
        ("decision-register/DEC-007-billing.yaml", """id: DEC-007
status: accepted
scope: service
effective_date: 2025-04-01
target_service: billing-service
audiences:
  - https://billing.example.com/api
algorithms:
  - RS256
  - ES256
"""),
        ("decision-register/DEC-008-inventory-search.yaml", """id: DEC-008
status: accepted
scope: edge
effective_date: 2025-06-20
source:
  service: inventory-service
  environment: production
  method: GET
  path: /search/index
target_service: search-service
audiences:
  - https://search.example.com/index
"""),
    ]
    return files


MIGRATION_THEMES = [
    (
        "Certificate-bound service identity",
        (
            "Mesh sidecars validated client certificate subjects and serial numbers at every hop. "
            "Gateway policy must retire those fields and bind audiences to OIDC issuer claims instead."
        ),
    ),
    (
        "OIDC discovery trust boundary",
        (
            "Offline discovery snapshots must preserve semantic issuer URLs while transport endpoints "
            "stay on loopback fixtures. Policy output must never echo fixture hosts or ports."
        ),
    ),
    (
        "JWKS key hygiene",
        (
            "Only asymmetric signing keys with verify operations belong in gateway policy. "
            "Encryption-only keys, octet HMAC material, and algorithms such as none or HS256 are rejected."
        ),
    ),
    (
        "Parallel edge authorization",
        (
            "Production and staging routes between the same services remain distinct when method, path, "
            "or authz_scope differ. Collapsing parallel edges merges incompatible audience requirements."
        ),
    ),
    (
        "Dossier authority precedence",
        (
            "Accepted and amended decisions outrank superseded notes. Scope ordering edge over service "
            "over environment prevents stale global defaults from overriding explicit route policy."
        ),
    ),
    (
        "Explicit deny propagation",
        (
            "Refund and administrative routes carry hard denies that must survive migration. "
            "A global audience shortcut must not reopen payment or admin surfaces."
        ),
    ),
    (
        "Service alias normalization",
        (
            "Graph aliases such as auth-svc must resolve to canonical service names before policy emission "
            "so audit rows, YAML edges, and dossier keys remain joinable."
        ),
    ),
    (
        "Audit coverage recursion",
        (
            "The coverage_gaps view must be empty after migration. Recursive SQL checks prove every "
            "deployable graph edge received an allow or deny action in the emitted gateway bundle."
        ),
    ),
    (
        "Issuer rotation compatibility",
        (
            "Two bundled OIDC revisions rotate JWKS URIs while keeping the semantic issuer stable. "
            "Migrators must read revision metadata without pinning transport URLs into policy."
        ),
    ),
    (
        "Idempotent policy emission",
        (
            "Repeated migrate-policy runs must yield byte-identical gateway YAML so automation can "
            "detect drift. Runtime state belongs under the configured migrator runtime directory."
        ),
    ),
]


SERVICE_NOTES = {
    "api-gateway": "terminates north-south traffic and forwards bearer tokens to mesh backends",
    "auth-service": "validates OIDC tokens and exchanges legacy mesh identities",
    "user-service": "serves profile APIs with environment-specific audience contracts",
    "billing-service": "owns account ledgers and exposes billing audiences to dependents",
    "inventory-service": "indexes stock levels and fans out to search replicas",
    "payment-service": "handles refunds under an explicit deny posture during migration",
    "search-service": "indexes catalog documents for inventory lookups",
}


def arch_review_body(index: int) -> str:
    title = f"ARCH-{index:03d}"
    dec = f"DEC-{((index % 8) + 1):03d}"
    revision = "google-revision-a" if index % 2 else "google-revision-b"
    body = f"# Architecture review {title}\n\n"
    body += (
        "This review records security constraints for retiring mutual TLS hop validation "
        "in favor of OIDC bearer enforcement at the gateway.\n\n"
    )
    body += "## Scope\n\n"
    body += (
        "The cutover affects service-to-service authorization, offline identity-provider "
        "metadata, and the SQLite audit trail that proves full edge coverage.\n\n"
    )
    body += "## Decision references\n\n"
    body += f"Authoritative routing and audience choices remain in decision-register entries, especially {dec}.\n\n"
    for offset in range(12):
        theme_idx = (index + offset) % len(MIGRATION_THEMES)
        heading, detail = MIGRATION_THEMES[theme_idx]
        service = list(SERVICE_NOTES.keys())[(index + offset) % len(SERVICE_NOTES)]
        service_note = SERVICE_NOTES[service]
        body += f"### {heading} ({title}-{offset + 1})\n\n"
        body += (
            f"{detail} During review {title}-{offset + 1}, engineers traced how {service} "
            f"{service_note} under {revision}. The note also records that payment-service "
            f"refund routes remain denied and retired admin-api must stay out of allow policy.\n\n"
        )
    body += "## Cross-reference\n\n"
    body += f"Coordinate with {dec} and migration-contract invariants before approving gateway YAML.\n"
    return body


def pad_dossier() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Generate indexed dossier reviews that satisfy long-context reading requirements."""
    out: list[tuple[str, str]] = []
    index_entries: list[tuple[str, str]] = []
    for i in range(1, 41):
        path = f"architecture/ARCH-{i:03d}-review.md"
        out.append((path, arch_review_body(i)))
        index_entries.append((f"ARCH-{i:03d}", path))
    return out, index_entries


def main() -> None:
    install_graphml()
    write(APP / "input" / "legacy-authz.yaml", legacy_yaml())
    write(APP / "input" / "gateway-policy.yaml", "schema_version: 1\nclient_cert_subject: CN=legacy\n")

    write(CANONICAL / "policy-contract.json", json.dumps({
        "allowed_algorithms": ["RS256", "ES256"],
        "allowed_key_types": ["RSA", "EC"],
        "retired_mtls_fields": ["client_cert_subject", "ca_bundle", "serial_number", "mtls_trust_bundle"],
        "audience_suffix": "",
    }, indent=2) + "\n")
    write(CANONICAL / "alias-register.json", json.dumps({
        "aliases": {"auth-svc": "auth-service", "auth_svc": "auth-service"}
    }, indent=2) + "\n")
    write(CANONICAL / "algorithm-policy.json", json.dumps({"forbidden": ["none", "HS256", "HS384", "HS512"]}, indent=2) + "\n")
    write(CANONICAL / "retirement-register.json", json.dumps({"retired_services": ["admin-api"]}, indent=2) + "\n")
    write(CANONICAL / "topology-contract.json", json.dumps({
        "edge_identity_fields": ["id", "source", "target", "environment", "method", "path", "authz_scope"]
    }, indent=2) + "\n")

    write(AUTH / "decision-authority.json", json.dumps({
        "authoritative_statuses": ["accepted", "amended"],
        "scope_order": ["edge", "service", "environment", "global"],
    }, indent=2) + "\n")
    write(AUTH / "decision-scope-schema.json", json.dumps({"scopes": ["edge", "service", "environment", "global"]}, indent=2) + "\n")

    for rev, fn in [("google-revision-a", oidc_revision_a), ("google-revision-b", oidc_revision_b)]:
        disc, jwks = fn()
        base = OIDC / rev
        write(base / "openid-configuration.json", json.dumps(disc, indent=2) + "\n")
        write(base / "jwks.json", json.dumps(jwks, indent=2) + "\n")
        write(base / "transport.json", json.dumps({"listen": "127.0.0.1:18081"}, indent=2) + "\n")

    write(OIDC / "compatibility.json", json.dumps({"revisions": ["google-revision-a", "google-revision-b"]}, indent=2) + "\n")

    index_entries = []
    for rel, content in dossier_files():
        write(DOSSIER / rel, content)
        dec_id = next(
            ln.split(": ", 1)[1] for ln in content.splitlines() if ln.startswith("id:")
        )
        index_entries.append((dec_id, rel))

    pad_files, pad_index = pad_dossier()
    for rel, content in pad_files:
        write(DOSSIER / rel, content)

    idx = "decisions:\n"
    for dec_id, rel in index_entries:
        idx += f"  - id: {dec_id}\n    path: {rel}\n"
    for arch_id, rel in pad_index:
        idx += f"  - id: {arch_id}\n    path: {rel}\n"
    write(DOSSIER / "index.yaml", idx)

    write(DOSSIER / "authority-policy.md", "# Dossier authority\n\nOnly accepted and amended decisions are authoritative.\n")
    write(APP / "docs" / "migration-contract.md", "# Migration contract\n\nOutputs: gateway-policy.yaml, migration-audit.db, migration-summary.json.\n")
    write(APP / "docs" / "topology-contract.md", "# Topology contract\n\nEdge identity uses graph edge id plus source, target, environment, method, path, authz_scope.\n")
    write(APP / "docs" / "dossier-precedence.md", "# Dossier precedence\n\nexplicit deny > accepted edge > accepted service > environment > global.\n")
    write(APP / "docs" / "oidc-contract.md", "# OIDC contract\n\nPolicy records semantic issuer and JWKS URI from discovery, not loopback transport URLs.\n")

    write(CANONICAL / "fixture-checksums.json", json.dumps(checksums(CANONICAL), indent=2, sort_keys=True) + "\n")
    write(OIDC / "fixture-checksums.json", json.dumps(checksums(OIDC), indent=2, sort_keys=True) + "\n")
    write(AUTH / "fixture-checksums.json", json.dumps(checksums(AUTH), indent=2, sort_keys=True) + "\n")

    print("fixtures generated")


if __name__ == "__main__":
    main()
