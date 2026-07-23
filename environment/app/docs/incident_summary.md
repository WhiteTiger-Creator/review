# Incident summary

During a staged production cutover, three PostgreSQL clusters were scheduled for
bootstrap from checked-in manifests. Local YAML and TOML described application
roles, databases, extensions, privileges, HBA rows, and maintenance settings.
Organization policy was supposed to arrive from an internal policy snapshot
service running on localhost during the release window.

The previous bootstrap tool ignored that policy path. As a result, required
owner and monitoring roles were omitted, forbidden direct CONNECT grants to
login roles were accepted, extension prerequisites such as `cube` for
`earthdistance` and `shared_preload_libraries` for `pg_stat_statements` were
left unresolved, HBA first-match order drifted when mandatory reject rows were
absent, and CREATE DATABASE / ALTER SYSTEM statements were incorrectly wrapped
inside transactional phases.

Release engineering paused the cutover and asked for a deterministic planner
that:

1. Fetches one verified policy snapshot per distinct environment.
2. Validates raw fragment response digests before parsing.
3. Merges local and policy resources with explicit prohibition and forced-value
   precedence.
4. Builds a dependency-aware operation graph with transaction-safe phases.
5. Emits canonical SQL plus a machine-readable plan whose SQL digest matches the
   exact written bytes.

The supplied fixtures represent a compact incident reconstruction: one accepted
production application cluster, one intentionally rejected production cluster
with a forbidden login-role privilege, and one smaller accepted staging cluster
that must continue planning after the rejection. All normative rules live in the
public profile documents. This narrative does not add hidden requirements and
does not include expected plan or SQL content.
