# Bootstrap policy profile

This document is the normative bounded profile for the PostgreSQL bootstrap
planner. It deliberately simplifies broader PostgreSQL behavior.

## Supported resource kinds

Clusters, roles, role memberships, databases, extensions, privileges, HBA
rules, and maintenance settings.

## Identifier rules

Identifiers are nonempty UTF-8 strings. Within one cluster, `role_id`,
`role_name`, `database_id`, `database_name`, and each resource-kind ID must be
unique. Physical YAML or TOML order is not semantic.

## Environments

Allowed cluster environments are exactly `development`, `staging`, and
`production`.

After local YAML and object-shape validation succeeds, collect the distinct
cluster environment strings and process them in ascending UTF-8 order. A
well-formed nonempty environment string outside the supported set causes the
whole run to fail with `unknown_local_environment`; the fatal detail is the
exact unrecognized string. This check occurs before any policy API request.

`invalid_enum_token` does not apply to the cluster `environment` field. It
continues to apply to the other bounded enum-token fields defined in
`input_schema.md`.

## Local YAML (`clusters.yaml`)

Root object contains exactly `clusters` (nonempty array). Each cluster contains
exactly: `cluster_id`, `environment`, `roles`, `role_memberships`, `databases`,
`extensions`, `privileges`, `hba_rules`.

### Roles

Fields: `role_id`, `role_name`, `login`, `inherit`, `createdb`, `createrole`,
`replication`, `bypassrls`, `connection_limit` (integer ≥ -1; `-1` means
unlimited).

### Role memberships

Fields: `membership_id`, `member_role_id`, `granted_role_id`. Directed edge is
`member_role_id → granted_role_id`. Self-membership is a cycle.

### Databases

Fields: `database_id`, `database_name`, `owner_role_id`, `template`
(`template0` or `template1`), `encoding`, `connection_limit`,
`environment_allowlist` (nonempty unique array of environments).

### Extensions

Fields: `extension_request_id`, `database_id`, `extension_id`, `version`
(exact string; no ranges, latest, wildcards, or null).

### Privileges

Fields: `grant_id`, `scope` (`database`|`schema`|`table`), `database_id`,
`schema_name_or_null`, `table_name_or_null`, `grantee_role_id`, `privileges`
(nonempty unique array), `grant_option`.

Scope field rules:

- database: both name fields null; privileges from `CONNECT`, `CREATE`
- schema: schema non-null, table null; privileges from `USAGE`, `CREATE`
- table: both names non-null; privileges from `SELECT`, `INSERT`, `UPDATE`,
  `DELETE`

Public privilege sort order (not alphabetical): `CONNECT`, `CREATE`, `USAGE`,
`SELECT`, `INSERT`, `UPDATE`, `DELETE`.

### HBA rules

Fields: `hba_id`, `connection_type` (`local`|`host`|`hostssl`),
`database_selector` (`all` or exact `database_id`), `role_selector` (`all` or
exact `role_id`), `ipv4_cidr_or_null`, `auth_method`
(`reject`|`peer`|`scram-sha-256`|`cert`), `priority`.

`local` requires null CIDR. `host`/`hostssl` require a normalized IPv4 CIDR.
No IPv6, hostnames, regexes, comma selectors, or include files.

Local rows are normalized with `source = local` and `mandatory = false`.

## Local TOML (`maintenance.toml`)

Repeated `[[settings]]` tables with: `setting_id`, `cluster_id`, `scope`
(`system`|`database`|`role`|`role_database`), `database_id_or_null`,
`role_id_or_null`, `setting_name`, `value`.

Scope reference requirements:

- system: both null
- database: database non-null, role null
- role: role non-null, database null
- role_database: both non-null

Absent optional keys mean null. TOML physical order is not semantic.

## Extension catalogue

Supported IDs: `pgcrypto`, `uuid-ossp`, `cube`, `earthdistance`,
`pg_stat_statements`.

Each entry: `extension_id`, `allowed_versions`, `requires`, `trusted`,
`required_settings`. Bounded rules include `earthdistance` requires `cube`, and
`pg_stat_statements` requires system `shared_preload_libraries` containing
`pg_stat_statements`.

Automatically injected dependency extensions must have exactly one allowed
version.

## Setting catalogue

Supported names: `shared_preload_libraries`, `max_connections`,
`log_min_duration_statement`, `statement_timeout`,
`idle_in_transaction_session_timeout`, `default_transaction_read_only`.

Each entry: `setting_name`, `value_type` (`integer`|`boolean`|`string`|
`string_array`), `allowed_scopes`, integer bounds or null,
`activation_mode` (`immediate`|`reload`|`restart`|`new_session`),
`transaction_compatible`.

## Policy merge

Process distinct environments in UTF-8 byte order, once each. Fetch fragments
in fixed order: `identity`, `database`, `access`.

### Identity fragment

`required_roles`, `role_constraints`, `required_memberships`,
`forbidden_memberships`.

### Database fragment

`required_databases`, `database_constraints`, `required_extensions`,
`setting_policies`.

### Access fragment

`required_privileges`, `privilege_rules`, `mandatory_hba_rules`.

Mandatory HBA rows: `source = policy`, `mandatory = true`.

## Merge precedence

1. explicit organization prohibition
2. organization-forced field value
3. explicit local field value
4. organization-required or organization-default value
5. bounded built-in default

Source tokens: `local`, `policy_required`, `merged`.

Organization-required resources are injected. Exact semantic duplicates are
deduplicated. Same ID with incompatible identity rejects the cluster.
Prohibitions always outrank forced true values. Never silently weaken a
forbidden request.

Exact-role constraints override wildcard (`*`) constraints for the same field.

## Required privilege injection and source matrix

`required_privileges` from the access fragment are injected unconditionally for
the cluster's environment. After resource merge, every privilege row's
`database_id` and `grantee_role_id` must exist among merged databases and roles.
A missing target rejects the cluster with `privilege_target_unavailable`.

Privilege checks by final `source` token:

| Final privilege source | Allowed-privilege check | Grant-option ban | Direct-login-role ban |
|---|---|---|---|
| `local` | yes | yes | yes |
| `policy_required` | yes | yes | no |
| `merged` | yes | yes | no |

Organization-required privileges are organization-authorized **only** for the
`forbid_direct_login_role_grants` rule. They do **not** bypass schema, target,
allowed-privilege, or grant-option checks.

## Maximum connection-limit formula

A maximum-connection constraint is violated exactly when:

`maximum_connection_limit_or_null != null`
AND `connection_limit != -1`
AND `connection_limit > maximum_connection_limit_or_null`

Apply that same formula to both roles and databases. Examples:

- `connection_limit = -1`, maximum = 50: valid (unlimited)
- `connection_limit = 50`, maximum = 50: valid
- `connection_limit = 51`, maximum = 50: violation

## Cluster independence

Plan clusters by `cluster_id` ascending UTF-8 bytes. Whole-run failures abort
everything. Cluster semantic failures reject only that cluster and continue.

Rejected clusters emit one cluster row, one rejection row, and no resource,
operation, phase, or SQL content.

## Role dependencies

Validate uniqueness, membership endpoints, owners, grantees, role-scoped
settings, and exact HBA role selectors. Reject self-membership, direct cycles,
indirect cycles, and forbidden memberships. Report sorted cycle member IDs.

## Database rules

Owner must exist. Cluster environment must be in allowlist. Create each
database in its own nontransactional phase. Database creation depends on owner
role creation.

## Extension closure

Union local and policy requests. Recursively inject catalogue `requires`
dependencies. Reject unknown extension, disallowed version, local/policy
version conflict, non-deterministic dependency version, dependency cycle, or
unavailable database.

Order by dependency topology; tie-break by `extension_id`, then `version`, then
`extension_request_id` (UTF-8). Dependency precedes dependent.

## Extension-setting coupling

After settings resolve, verify each extension `required_settings`. Contains
checks require a string array containing the exact token. Equals checks require
normalized equality. Do not inject extension-required settings unless also
marked required by organization setting policy.

## Privilege resolution

Semantic identity: scope, database, schema, table, grantee, grant_option.
Combine privileges for identical identities using the public privilege order.
Validate targets, allowed privileges, grant option, and the direct-login ban
using the privilege-source matrix above.

## HBA containment

- database: `all` contains every exact selector; exact contains only itself
- role: same rule
- address: local only comparable to local; host/hostssl use IPv4 CIDR
  containment (`A` contains `B` when every address in `B` is inside `A`)
- connection class: local↔local, host↔host, hostssl↔hostssl only. Host does
  **not** contain hostssl for shadow analysis.

## HBA ordering

Sort HBA rows by this exact ascending tuple (first key wins):

1. mandatory policy reject row first (`mandatory && auth_method == reject`
   sorts before every other row)
2. database selector: `all` before exact (`all` rank 0, exact rank 1)
3. role selector: `all` before exact (`all` rank 0, exact rank 1)
4. IPv4 CIDR prefix length descending (longer / narrower first; local rows and
   missing CIDR use width sentinel that does not outrank real widths)
5. connection class rank descending: `hostssl` before `host` before `local`
6. policy source before local
7. priority descending
8. `hba_id` ascending UTF-8

Do not invert steps 2–3. Catchall (`all`) selectors sort before exact
selectors. Skip CIDR-width comparison for local rows.

## HBA shadow detection

After ordering, a later row is fully shadowed when an earlier row contains its
connection class, database selector, role selector, and address selector.
Auth methods need not match. Reject with `hba_rule_fully_shadowed` using the
first earlier shadowing row. Details: `shadowed_hba_id`, `shadowing_hba_id`.

## Setting resolution

Order: forbidden → forced → local → required/default → documented default.
Reject settings according to the decision tree in **Setting validation reason
tokens** below. In short:

- Unknown catalog name or invalid value type: `invalid_setting_type`
- Known catalog setting with valid type but prohibited scope:
  `invalid_setting_scope`
- Out-of-bounds integers, missing required values, and forbidden settings:
  `setting_outside_policy_bounds` (and related existing tokens)

Array values: deduplicate exact strings, sort UTF-8 bytes.
`shared_preload_libraries` emits as one comma-separated SQL string.
Restart activation marks restart required without emitting a restart command.
Reload activation (or any HBA rows) yields one final `configuration_reload`
phase when needed.

## Setting validation reason tokens

Normative distinction between `invalid_setting_type` and
`invalid_setting_scope`. Catalog / type checks that resolve the setting name
run before scope checks. A setting name that cannot be found in the selected
setting catalog is **not** classified as `invalid_setting_scope`. It is
classified as `invalid_setting_type` because no catalog type definition exists
against which the value can be validated or normalized.

### `invalid_setting_type`

Emitted when:

1. The setting name is absent from the selected setting catalog (unknown
   catalog setting name).
2. The setting name resolves, but the catalog-declared `value_type` is not one
   of the supported tokens `integer`, `boolean`, `string`, or `string_array`
   (normalization cannot proceed under a declared type).

Scalar JSON representations for a *supported* declared type are coerced by the
bounded profile (they are not rejected as `invalid_setting_type`). Integer
bounds failures use `setting_outside_policy_bounds`, not this token.

### `invalid_setting_scope`

Used only after the setting name successfully resolves to a known catalog
entry. Emitted when the setting cannot be applied at the requested scope:

1. The requested scope token is not present in the catalog entry's
   `allowed_scopes`.
2. Scope is `database` but `database_id_or_null` does not identify a database
   merged into the cluster.
3. Scope is `role` or `role_database` but `role_id_or_null` does not identify a
   role merged into the cluster.
4. Scope is `role_database` but `database_id_or_null` does not identify a
   database merged into the cluster.

### Decision tree

1. Parse the setting row structure.
2. Look up the setting name in the selected setting catalog.
3. When the setting name is unknown: reason = `invalid_setting_type`.
4. Validate that the known setting is permitted at the requested scope
   (`allowed_scopes` and referenced database/role availability).
5. When scope validation fails: reason = `invalid_setting_scope`.
6. Apply policy forcing / forbidden / integer bound checks
   (`setting_outside_policy_bounds` when those fail).
7. Normalize the value under the catalog-declared type. When the declared
   `value_type` is unsupported: reason = `invalid_setting_type`.
8. Otherwise continue with merge precedence, operation generation, and phase
   rules.

Type/catalog name resolution occurs before scope validation.

### Setting-error matrix

| Condition | Reason token | Whole-run or cluster-level | `resource_id_or_null` | Required details fields | Next-stage behavior |
|---|---|---|---|---|---|
| Unknown setting catalog name | `invalid_setting_type` | cluster-level rejection | setting ID | `{}` | stop this cluster; later clusters continue |
| Known setting, catalog `value_type` not in `{integer,boolean,string,string_array}` | `invalid_setting_type` | cluster-level rejection | setting ID | `{}` | stop this cluster; later clusters continue |
| Known setting, permitted type path, forbidden or unresolvable scope | `invalid_setting_scope` | cluster-level rejection | setting ID | `{}` | stop this cluster; later clusters continue |

These tokens are cluster-level rejections (not whole-run fatal). See
`rejection_precedence.md` for the global stage rank list and a cross-reference
to this section.

## Operation kinds

Exactly: `create_role`, `grant_role_membership`, `alter_system_setting`,
`create_database`, `connect_database`, `create_extension`,
`grant_database_privilege`, `grant_schema_privilege`, `grant_table_privilege`,
`alter_database_setting`, `alter_role_setting`, `alter_role_database_setting`,
`emit_hba_rule`, `reload_configuration`.

Operation ID forms:

- `role:<cluster_id>:<role_id>`
- `membership:<cluster_id>:<membership_id>`
- `system-setting:<cluster_id>:<setting_id>`
- `database:<cluster_id>:<database_id>`
- `connect:<cluster_id>:<database_id>`
- `extension:<cluster_id>:<database_id>:<extension_id>`
- `privilege:<cluster_id>:<grant_id>`
- `database-setting:<cluster_id>:<setting_id>`
- `role-setting:<cluster_id>:<setting_id>`
- `role-database-setting:<cluster_id>:<setting_id>`
- `hba:<cluster_id>:<hba_id>`
- `reload:<cluster_id>`

## Operation dependencies

- create_role precedes memberships, owned databases, grants to that role, role
  settings, role_database settings, and exact-role HBA rows
- create_database precedes connect_database
- connect_database precedes extensions, database/schema/table privileges,
  database and role_database settings, and exact-database HBA rows
- required extension precedes dependent extension
- required system setting precedes extensions that require it
- all reload-requiring settings and all HBA emits precede reload_configuration

Reject remaining operation cycles with `operation_dependency_cycle`.

## Topological ordering

Deterministic Kahn-style selection among ready operations by:

1. phase rank ascending
2. cluster_id ascending
3. database_id_or_null with null first
4. operation-kind rank ascending
5. resource_id ascending
6. operation_id ascending

Phase ranks: `cluster_transaction=0`, `system_nontransactional=1`,
`database_create_nontransactional=2`, `database_transaction=3`,
`configuration_reload=4`.

Operation-kind ranks: create_role=0, grant_role_membership=1,
alter_system_setting=2, create_database=3, connect_database=4,
create_extension=5, grant_database_privilege=6, grant_schema_privilege=7,
grant_table_privilege=8, alter_database_setting=9, alter_role_setting=10,
alter_role_database_setting=11, emit_hba_rule=12, reload_configuration=13.

## Phase construction

- `cluster_transaction`: roles and memberships; transactional; one per accepted
  cluster when nonempty
- `system_nontransactional`: exactly one ALTER SYSTEM; nontransactional
- `database_create_nontransactional`: exactly one CREATE DATABASE
- `database_transaction`: connect plus database-scoped ops for one database;
  transactional; `\connect` before BEGIN
- `configuration_reload`: HBA comments then `SELECT pg_reload_conf()`; at most
  one per cluster; omit when no HBA and no reload-requiring setting

Never place CREATE DATABASE or ALTER SYSTEM inside BEGIN/COMMIT.

### Local environment fatal

`unknown_local_environment` is emitted when a cluster contains a successfully
parsed nonempty `environment` string other than `development`, `staging`, or
`production`.

The fatal detail is the exact unknown string.

This check is performed after local structural validation and before policy
snapshot fetching.

It is distinct from `invalid_enum_token`, which applies to the other bounded
enum fields documented in `input_schema.md`.

## Whole-run fatal tokens (first-failure order)

`missing_required_input`, `malformed_yaml`, `malformed_toml`,
`malformed_extension_catalog`, `malformed_setting_catalog`,
`duplicate_cluster_id`, `duplicate_local_resource_id`, `invalid_local_schema`,
`invalid_enum_token`, `unknown_local_environment`, `policy_api_unavailable`,
`policy_api_timeout`, `policy_api_redirect_forbidden`, `policy_api_status_error`,
`policy_api_content_type_invalid`, `policy_manifest_invalid`,
`missing_policy_fragment`, `duplicate_policy_fragment`,
`unknown_policy_fragment`, `invalid_fragment_digest`,
`fragment_digest_mismatch`, `malformed_policy_fragment`,
`fragment_id_mismatch`, `policy_revision_mismatch`,
`policy_environment_mismatch`, `invalid_policy_document`,
`output_write_failed`.

Validate all local files first, then fetch environments, then fragments in
identity → database → access order.

## Cluster rejection tokens (first-failure order)

`resource_identity_conflict`, `forbidden_role_capability`,
`role_constraint_violation`, `forbidden_membership`, `role_membership_cycle`,
`database_owner_unavailable`, `database_environment_forbidden`,
`database_constraint_violation`, `unknown_extension`,
`extension_dependency_missing`, `extension_dependency_cycle`,
`extension_version_conflict`, `required_extension_setting_unsatisfied`,
`forbidden_privilege`, `privilege_target_unavailable`, `invalid_setting_scope`,
`invalid_setting_type`, `setting_outside_policy_bounds`,
`hba_reference_unavailable`, `hba_rule_fully_shadowed`,
`operation_dependency_cycle`.
