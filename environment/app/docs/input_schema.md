# Local input schema

Normative schema for the four local inputs under `/app/data`. Identifiers are
nonempty UTF-8 strings. An empty required identifier is `invalid_local_schema`.
Cluster IDs are not restricted to fixture naming patterns; values such as
`prod-app-01` are valid.

Unknown fields are **rejected** with `invalid_local_schema`. The rule is
identical in the Rust oracle, Python reference model, and verifier expectations:
only the keys listed below may appear at each object level.

Physical array or table order is **not** semantic in any local file.

## `clusters.yaml`

Top-level object with exactly one key:

| Key | Type | Required |
|---|---|---|
| `clusters` | nonempty array of cluster objects | yes |

Each cluster object contains exactly these keys:

| Key | Type | Required | Notes |
|---|---|---|---|
| `cluster_id` | string | yes | nonempty; unique across the file |
| `environment` | string | yes | `development`, `staging`, or `production` |
| `roles` | array | yes | may be empty |
| `role_memberships` | array | yes | may be empty |
| `databases` | array | yes | may be empty |
| `extensions` | array | yes | may be empty |
| `privileges` | array | yes | may be empty |
| `hba_rules` | array | yes | may be empty |

### Role object

| Key | Type | Required |
|---|---|---|
| `role_id` | string | yes |
| `role_name` | string | yes |
| `login` | boolean | yes |
| `inherit` | boolean | yes |
| `createdb` | boolean | yes |
| `createrole` | boolean | yes |
| `replication` | boolean | yes |
| `bypassrls` | boolean | yes |
| `connection_limit` | integer | yes | ≥ `-1`; `-1` means unlimited. A policy maximum is violated exactly when `maximum_connection_limit_or_null != null` AND `connection_limit != -1` AND `connection_limit > maximum_connection_limit_or_null`. |

Identity keys within a cluster: `role_id` (unique), `role_name` (unique).

### Role membership object

| Key | Type | Required |
|---|---|---|
| `membership_id` | string | yes |
| `member_role_id` | string | yes |
| `granted_role_id` | string | yes |

Identity keys: `membership_id` (unique). Directed edge is
`member_role_id → granted_role_id`.

### Database object

| Key | Type | Required |
|---|---|---|
| `database_id` | string | yes |
| `database_name` | string | yes |
| `owner_role_id` | string | yes |
| `template` | string | yes | `template0` or `template1` |
| `encoding` | string | yes |
| `connection_limit` | integer | yes | ≥ `-1`; same unlimited/`-1` maximum-limit formula as roles |
| `environment_allowlist` | array of strings | yes | nonempty; unique entries |

Identity keys: `database_id` (unique), `database_name` (unique).

### Extension request object

| Key | Type | Required |
|---|---|---|
| `extension_request_id` | string | yes |
| `database_id` | string | yes |
| `extension_id` | string | yes |
| `version` | string | yes | exact catalogue version; no wildcards |

Identity keys: `extension_request_id` (unique). Semantic key
`(database_id, extension_id)` must not carry conflicting versions after merge.

### Privilege object

| Key | Type | Required |
|---|---|---|
| `grant_id` | string | yes |
| `scope` | string | yes | `database`, `schema`, or `table` |
| `database_id` | string | yes |
| `schema_name_or_null` | string or null | yes |
| `table_name_or_null` | string or null | yes |
| `grantee_role_id` | string | yes |
| `privileges` | array of strings | yes | nonempty; unique |
| `grant_option` | boolean | yes |

Scope reference rules:

- `database`: both name fields null; privileges from `CONNECT`, `CREATE`
- `schema`: `schema_name_or_null` non-null, `table_name_or_null` null;
  privileges from `USAGE`, `CREATE`
- `table`: both names non-null; privileges from `SELECT`, `INSERT`, `UPDATE`,
  `DELETE`

Identity key: `grant_id` (unique).

### HBA rule object

| Key | Type | Required |
|---|---|---|
| `hba_id` | string | yes |
| `connection_type` | string | yes | `local`, `host`, or `hostssl` |
| `database_selector` | string | yes | `all` or exact `database_id` |
| `role_selector` | string | yes | `all` or exact `role_id` |
| `ipv4_cidr_or_null` | string or null | yes |
| `auth_method` | string | yes | `reject`, `peer`, `scram-sha-256`, or `cert` |
| `priority` | integer | yes |

`local` requires null CIDR. `host`/`hostssl` require a normalized IPv4 CIDR.

Identity key: `hba_id` (unique).

### Cluster duplicate rules

Duplicate `cluster_id` across the file → `duplicate_cluster_id`.

Duplicate resource IDs of the same kind within one cluster →
`duplicate_local_resource_id`.

Invalid enum tokens (environment, template, scope, connection_type,
auth_method, privilege names) → `invalid_enum_token`.

## `maintenance.toml`

Top-level `settings` array (may be empty). Each `[[settings]]` table:

| Key | Type | Required |
|---|---|---|
| `setting_id` | string | yes |
| `cluster_id` | string | yes |
| `scope` | string | yes | `system`, `database`, `role`, or `role_database` |
| `database_id_or_null` | string or null | no | default null |
| `role_id_or_null` | string or null | no | default null |
| `setting_name` | string | yes |
| `value` | JSON-compatible value | yes |

Scope reference requirements:

- `system`: both reference fields absent or null
- `database`: `database_id_or_null` non-null, `role_id_or_null` null
- `role`: `role_id_or_null` non-null, `database_id_or_null` null
- `role_database`: both non-null

Identity key: `setting_id` (unique across the entire file).

## `extension_catalog.json`

Top-level object:

| Key | Type | Required |
|---|---|---|
| `extensions` | array | yes |

Each entry:

| Key | Type | Required |
|---|---|---|
| `extension_id` | string | yes |
| `allowed_versions` | array of strings | yes | nonempty |
| `requires` | array of strings | yes | may be empty |
| `trusted` | boolean | yes |
| `required_settings` | array | yes | may be empty |

Each `required_settings` element:

| Key | Type | Required |
|---|---|---|
| `setting_name` | string | yes |
| `scope` | string | yes |
| `required_value_contains_or_null` | string or null | yes |
| `required_value_equals_or_null` | any or null | yes |

Identity key: `extension_id` (unique).

## `setting_catalog.json`

Top-level object:

| Key | Type | Required |
|---|---|---|
| `settings` | array | yes |

Each entry:

| Key | Type | Required |
|---|---|---|
| `setting_name` | string | yes |
| `value_type` | string | yes | `integer`, `boolean`, `string`, or `string_array` |
| `allowed_scopes` | array of strings | yes | nonempty |
| `minimum_integer_or_null` | integer or null | yes |
| `maximum_integer_or_null` | integer or null | yes |
| `activation_mode` | string | yes | `immediate`, `reload`, `restart`, or `new_session` |
| `transaction_compatible` | boolean | yes |

Identity key: `setting_name` (unique).

## Whole-run fatal tokens (local validation)

Validated before policy fetch. First matching failure aborts the entire run,
deletes outputs, and prints `<token>:` on stderr.

`missing_required_input`, `malformed_yaml`, `malformed_toml`,
`malformed_extension_catalog`, `malformed_setting_catalog`,
`duplicate_cluster_id`, `duplicate_local_resource_id`, `invalid_local_schema`,
`invalid_enum_token`, `unknown_local_environment`.

See `bootstrap_policy_profile.md` for policy-fetch and output fatals.
