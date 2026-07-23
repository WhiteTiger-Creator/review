# Policy fragment schema

Each environment snapshot has three fragments fetched in order: `identity`,
`database`, `access`. The `document` field of each fragment response is a JSON
object with only the keys defined below. Malformed nested policy objects →
`invalid_policy_document`.

Unknown fields inside fragment `document` objects are rejected with
`invalid_policy_document`.

## Identity fragment

Top-level keys (all required arrays; may be empty):

| Key | Type |
|---|---|
| `required_roles` | array of role objects |
| `role_constraints` | array of constraint objects |
| `required_memberships` | array of membership objects |
| `forbidden_memberships` | array of forbidden-edge objects |

### `required_roles` element

Same fields as a local role object, plus optional `source_id` (string,
nonempty when present). `source_id` is metadata only; it is not part of role
identity comparison.

### `role_constraints` element

| Key | Type | Required |
|---|---|---|
| `role_id_or_star` | string | yes | exact `role_id` or `*` |
| `forbidden_true_attributes` | array of strings | yes | may be empty |
| `forced_boolean_attributes` | object | yes | map of attribute name → boolean |
| `maximum_connection_limit_or_null` | integer or null | yes |

Forbidden attributes are drawn from: `login`, `inherit`, `createdb`,
`createrole`, `replication`, `bypassrls`. Forced attributes use the same names.

### `required_memberships` element

| Key | Type | Required |
|---|---|---|
| `membership_id` | string | yes |
| `member_role_id` | string | yes |
| `granted_role_id` | string | yes |

### `forbidden_memberships` element

| Key | Type | Required |
|---|---|---|
| `member_role_id` | string | yes |
| `granted_role_id` | string | yes |

## Database fragment

Top-level keys (all required arrays; may be empty):

| Key | Type |
|---|---|
| `required_databases` | array of database objects |
| `database_constraints` | array of constraint objects |
| `required_extensions` | array of extension request objects |
| `setting_policies` | array of policy objects |

### `required_databases` element

Same fields as a local database object, plus optional `source_id` (metadata
only).

### `database_constraints` element

| Key | Type | Required |
|---|---|---|
| `database_id_or_star` | string | yes | exact `database_id` or `*` |
| `forbidden_templates` | array of strings | yes | may be empty |
| `forced_encoding_or_null` | string or null | yes |
| `maximum_connection_limit_or_null` | integer or null | yes |
| `allowed_environments` | array of strings | yes | may be empty |

When `allowed_environments` is empty, the cluster environment alone is
checked.

### `required_extensions` element

Same fields as a local extension request object.

### `setting_policies` element

| Key | Type | Required |
|---|---|---|
| `setting_name` | string | yes |
| `scope_or_star` | string | yes | `system`, `database`, `role`, `role_database`, or `*` |
| `forced_value_or_null` | any or null | yes |
| `minimum_integer_or_null` | integer or null | yes |
| `maximum_integer_or_null` | integer or null | yes |
| `forbidden` | boolean | yes |
| `required` | boolean | yes |

## Access fragment

Top-level keys (all required arrays; may be empty):

| Key | Type |
|---|---|
| `required_privileges` | array of privilege objects |
| `privilege_rules` | array of rule objects |
| `mandatory_hba_rules` | array of HBA objects |

### `required_privileges` element

Same fields as a local privilege object, plus optional `source_id` (metadata
only).

### `privilege_rules` element

| Key | Type | Required |
|---|---|---|
| `scope` | string | yes | `database`, `schema`, or `table` |
| `allowed_privileges` | array of strings | yes | may be empty |
| `forbid_grant_option` | boolean | yes |
| `forbid_direct_login_role_grants` | boolean | yes |

### `mandatory_hba_rules` element

Same fields as a local HBA rule object. Injected rows use `source = policy`
and `mandatory = true`.

## Forced field application

Precedence for organization vs local field values:

1. organization prohibition (`forbidden_true_attributes`, `forbidden` setting
   policy, `forbidden_templates`, privilege rule bans)
2. organization-forced field value (`forced_boolean_attributes`,
   `forced_value_or_null`, `forced_encoding_or_null`)
3. explicit local field value
4. organization-required or organization-default value (injected
   `required_roles`, `required_databases`, `required_extensions`,
   `required_memberships`, `required_privileges`, required system settings)
5. bounded built-in default

Prohibitions always outrank forced true values. Never silently weaken a
forbidden request.

### Database forced encoding

When a winning `forced_encoding_or_null` is non-null for a database, it
replaces `database.encoding` before database rows and `CREATE DATABASE` SQL
are emitted.

### Constraint wildcard precedence

For `role_constraints` and `database_constraints`, an exact ID selector
(`role_id_or_star` or `database_id_or_star` equal to the resource ID) overrides
a `*` selector for the same field. Evaluate applicable constraints in order:
exact selectors first, then `*`.

### Setting policy evaluation order

Within setting resolution: forbidden → forced → local value →
required/default → catalogue default.

### Source tokens

Emitted resource rows use exactly one of: `local`, `policy_required`,
`merged`.

### Merge identity

- **Roles**: identity is the tuple `(login, inherit, createdb, createrole,
  replication, bypassrls, connection_limit)`. Same `role_id` with a different
  tuple → `resource_identity_conflict`.
- **Databases**: identity is `(database_name, owner_role_id, template,
  encoding)`. Same `database_id` with a different tuple →
  `resource_identity_conflict`.
- **Privileges**: semantic identity is `(scope, database_id, schema, table,
  grantee_role_id, grant_option)`. Identical identities merge privilege lists.
- Organization-required resources are injected when absent locally. Exact
  semantic duplicates deduplicate; incompatible duplicates reject.
