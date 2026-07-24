# Plan schema

`bootstrap_plan.json` top-level keys in this exact order:

`schema_version`, `policy_snapshot_rows`, `cluster_rows`, `role_rows`,
`membership_rows`, `database_rows`, `extension_rows`, `privilege_rows`,
`hba_rows`, `setting_rows`, `operation_rows`, `phase_rows`, `rejection_rows`,
`summary`, `sql_sha256`.

`schema_version` must equal `1`. Serialization: UTF-8 JSON, two-space
indentation, stable field order from typed structs, no trailing spaces, exactly
one trailing LF.

## policy_snapshot_rows

`environment`, `policy_revision`, `fragment_rows` where each fragment row is
`fragment_id`, `body_sha256`. Sort snapshots by environment. Sort fragments by
identity → database → access.

## cluster_rows

`cluster_id`, `environment`, `status` (`accepted`|`rejected`), `reason_or_null`,
`requires_reload`, `requires_restart`, and counts for roles, databases,
extensions, privileges, HBA, settings, operations, phases. Rejected clusters
have all counts zero and both require flags false. Sort by `cluster_id`.

## role_rows

`cluster_id`, `role_id`, `role_name`, `source`, boolean attributes,
`connection_limit`. Source: `local`|`policy_required`|`merged`. Sort by
cluster_id, role_id.

## membership_rows

`cluster_id`, `membership_id`, `member_role_id`, `granted_role_id`, `source`.
Sort by cluster_id, member_role_id, granted_role_id, membership_id.

## database_rows

`cluster_id`, `database_id`, `database_name`, `owner_role_id`, `template`,
`encoding`, `connection_limit`, `source`. Sort by cluster_id, database_id.

## extension_rows

`cluster_id`, `database_id`, `extension_id`, `version`, `selection_reason`
(`local`|`policy_required`|`merged`|`dependency`), `dependency_depth`,
`topological_position`. Sort by cluster_id, database_id, topological_position,
extension_id.

## privilege_rows

`cluster_id`, `grant_id`, `scope`, `database_id`, `schema_name_or_null`,
`table_name_or_null`, `grantee_role_id`, `privileges`, `grant_option`, `source`.
Privileges preserve public privilege order. Sort by cluster_id, database_id,
scope rank (database=0, schema=1, table=2), schema null first, table null first,
grantee_role_id, grant_id.

## hba_rows

`cluster_id`, `hba_position` (0-based), `hba_id`, `connection_type`,
`database_selector`, `role_selector`, `ipv4_cidr_or_null`, `auth_method`,
`source`, `mandatory`, `priority`. Sort by cluster_id, hba_position.

## setting_rows

`cluster_id`, `setting_id`, `scope`, `database_id_or_null`, `role_id_or_null`,
`setting_name`, `normalized_value` (JSON matching catalogue type),
`activation_mode`, `transaction_compatible`, `source`. Sort by cluster_id,
scope rank (system=0, database=1, role=2, role_database=3), database null first,
role null first, setting_name, setting_id.

## operation_rows

`cluster_id`, `operation_id`, `operation_kind`, `resource_id`,
`database_id_or_null`, `depends_on_operation_ids` (UTF-8 sorted),
`topological_position`, `phase_index`. Sort by cluster_id, topological_position,
operation_id.

## phase_rows

`cluster_id`, `phase_index` (0-based), `phase_kind`, `database_id_or_null`,
`transactional`, `operation_ids` (topo order), `requires_reload`,
`requires_restart`. Sort by cluster_id, phase_index.

## rejection_rows

`cluster_id`, `stage` (`merge`|`roles`|`databases`|`extensions`|`privileges`|
`settings`|`hba`|`graph`), `reason`, `resource_id_or_null`, `details` (JSON
object, no non-deterministic prose). Sort by cluster_id.

## summary

Exactly: `cluster_count`, `accepted_cluster_count`, `rejected_cluster_count`,
`policy_snapshot_count`, `role_count`, `membership_count`, `database_count`,
`extension_count`, `privilege_count`, `hba_count`, `setting_count`,
`operation_count`, `phase_count`, `reload_required_cluster_count`,
`restart_required_cluster_count`.

Derive every value from emitted rows.

## sql_sha256

Lowercase 64-character SHA-256 of the exact final bytes written to
`bootstrap.sql`, including the trailing LF.
