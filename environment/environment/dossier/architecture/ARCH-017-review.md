# Architecture review ARCH-017

This review records security constraints for retiring mutual TLS hop validation in favor of OIDC bearer enforcement at the gateway.

## Scope

The cutover affects service-to-service authorization, offline identity-provider metadata, and the SQLite audit trail that proves full edge coverage.

## Decision references

Authoritative routing and audience choices remain in decision-register entries, especially DEC-002.

### Audit coverage recursion (ARCH-017-1)

The coverage_gaps view must be empty after migration. Recursive SQL checks prove every deployable graph edge received an allow or deny action in the emitted gateway bundle. During review ARCH-017-1, engineers traced how billing-service owns account ledgers and exposes billing audiences to dependents under google-revision-a. The note also records that payment-service refund routes remain denied and retired admin-api must stay out of allow policy.

### Issuer rotation compatibility (ARCH-017-2)

Two bundled OIDC revisions rotate JWKS URIs while keeping the semantic issuer stable. Migrators must read revision metadata without pinning transport URLs into policy. During review ARCH-017-2, engineers traced how inventory-service indexes stock levels and fans out to search replicas under google-revision-a. The note also records that payment-service refund routes remain denied and retired admin-api must stay out of allow policy.

### Idempotent policy emission (ARCH-017-3)

Repeated migrate-policy runs must yield byte-identical gateway YAML so automation can detect drift. Runtime state belongs under the configured migrator runtime directory. During review ARCH-017-3, engineers traced how payment-service handles refunds under an explicit deny posture during migration under google-revision-a. The note also records that payment-service refund routes remain denied and retired admin-api must stay out of allow policy.

### Certificate-bound service identity (ARCH-017-4)

Mesh sidecars validated client certificate subjects and serial numbers at every hop. Gateway policy must retire those fields and bind audiences to OIDC issuer claims instead. During review ARCH-017-4, engineers traced how search-service indexes catalog documents for inventory lookups under google-revision-a. The note also records that payment-service refund routes remain denied and retired admin-api must stay out of allow policy.

### OIDC discovery trust boundary (ARCH-017-5)

Offline discovery snapshots must preserve semantic issuer URLs while transport endpoints stay on loopback fixtures. Policy output must never echo fixture hosts or ports. During review ARCH-017-5, engineers traced how api-gateway terminates north-south traffic and forwards bearer tokens to mesh backends under google-revision-a. The note also records that payment-service refund routes remain denied and retired admin-api must stay out of allow policy.

### JWKS key hygiene (ARCH-017-6)

Only asymmetric signing keys with verify operations belong in gateway policy. Encryption-only keys, octet HMAC material, and algorithms such as none or HS256 are rejected. During review ARCH-017-6, engineers traced how auth-service validates OIDC tokens and exchanges legacy mesh identities under google-revision-a. The note also records that payment-service refund routes remain denied and retired admin-api must stay out of allow policy.

### Parallel edge authorization (ARCH-017-7)

Production and staging routes between the same services remain distinct when method, path, or authz_scope differ. Collapsing parallel edges merges incompatible audience requirements. During review ARCH-017-7, engineers traced how user-service serves profile APIs with environment-specific audience contracts under google-revision-a. The note also records that payment-service refund routes remain denied and retired admin-api must stay out of allow policy.

### Dossier authority precedence (ARCH-017-8)

Accepted and amended decisions outrank superseded notes. Scope ordering edge over service over environment prevents stale global defaults from overriding explicit route policy. During review ARCH-017-8, engineers traced how billing-service owns account ledgers and exposes billing audiences to dependents under google-revision-a. The note also records that payment-service refund routes remain denied and retired admin-api must stay out of allow policy.

### Explicit deny propagation (ARCH-017-9)

Refund and administrative routes carry hard denies that must survive migration. A global audience shortcut must not reopen payment or admin surfaces. During review ARCH-017-9, engineers traced how inventory-service indexes stock levels and fans out to search replicas under google-revision-a. The note also records that payment-service refund routes remain denied and retired admin-api must stay out of allow policy.

### Service alias normalization (ARCH-017-10)

Graph aliases such as auth-svc must resolve to canonical service names before policy emission so audit rows, YAML edges, and dossier keys remain joinable. During review ARCH-017-10, engineers traced how payment-service handles refunds under an explicit deny posture during migration under google-revision-a. The note also records that payment-service refund routes remain denied and retired admin-api must stay out of allow policy.

### Audit coverage recursion (ARCH-017-11)

The coverage_gaps view must be empty after migration. Recursive SQL checks prove every deployable graph edge received an allow or deny action in the emitted gateway bundle. During review ARCH-017-11, engineers traced how search-service indexes catalog documents for inventory lookups under google-revision-a. The note also records that payment-service refund routes remain denied and retired admin-api must stay out of allow policy.

### Issuer rotation compatibility (ARCH-017-12)

Two bundled OIDC revisions rotate JWKS URIs while keeping the semantic issuer stable. Migrators must read revision metadata without pinning transport URLs into policy. During review ARCH-017-12, engineers traced how api-gateway terminates north-south traffic and forwards bearer tokens to mesh backends under google-revision-a. The note also records that payment-service refund routes remain denied and retired admin-api must stay out of allow policy.

## Cross-reference

Coordinate with DEC-002 and migration-contract invariants before approving gateway YAML.
