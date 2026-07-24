# Phase contract

Operations are assigned to execution phases after topological sorting. Phase
construction follows the global operation order (`topological_position`) while
grouping statements into the phase kinds below.

## Operation → phase mapping

| Operation kind | Phase kind |
|---|---|
| `create_role` | `cluster_transaction` |
| `grant_role_membership` | `cluster_transaction` |
| `alter_system_setting` | `system_nontransactional` |
| `create_database` | `database_create_nontransactional` |
| `connect_database` | `database_transaction` |
| `create_extension` | `database_transaction` |
| `grant_database_privilege` | `database_transaction` |
| `grant_schema_privilege` | `database_transaction` |
| `grant_table_privilege` | `database_transaction` |
| `alter_database_setting` | `database_transaction` |
| `alter_role_setting` | `database_transaction` |
| `alter_role_database_setting` | `database_transaction` |
| `emit_hba_rule` | `configuration_reload` |
| `reload_configuration` | `configuration_reload` |

Internal DAG operations may use kind `extension`; emitted `operation_rows` and
SQL use `create_extension`.

## Role-scoped settings

`alter_role_setting` operations keep `operation_rows.database_id_or_null = null`.
They are attached to the first `database_transaction` phase of the cluster (UTF-8
database order of emitted phases). When no database transaction phase exists,
they attach to `cluster_transaction`. This is metadata-only in the current SQL
serializer: no additional `ALTER ROLE ... SET` statement is emitted solely for
phase coherence.

`alter_role_database_setting` attaches to the matching database's
`database_transaction` phase.

`grant_table_privilege` is tracked in plan `operation_ids` for the target
database but is not rendered as executable SQL.


`create_database` operations set `database_id_or_null = null` on
`operation_rows`. The target database is identified by `resource_id`
(`database_id`). The corresponding `database_create_nontransactional` phase row
sets `database_id_or_null` to that database ID.

## Phase sequence

For each accepted cluster, emit phases in this order when nonempty:

1. `cluster_transaction` — at most one; all role and membership operations
2. `system_nontransactional` — one phase per system setting operation, in
   topological order
3. `database_create_nontransactional` — one phase per `create_database`, in
   topological order
4. `database_transaction` — one phase per database that has database-scoped
   operations beyond `connect_database`; databases in `database_id` ascending
   UTF-8
5. `configuration_reload` — at most one; omitted when no HBA rows and no
   reload-requiring settings

`phase_index` is 0-based and contiguous per cluster.

## `phase_rows` fields

| Field | Rule |
|---|---|
| `cluster_id` | owning cluster |
| `phase_index` | 0-based sequence |
| `phase_kind` | one of the five kinds above |
| `database_id_or_null` | set for `database_create_nontransactional` and `database_transaction`; null otherwise |
| `transactional` | `true` for `cluster_transaction` and `database_transaction`; `false` otherwise |
| `operation_ids` | operations in this phase, in topological order |
| `requires_reload` | `true` only for `configuration_reload` when emitted |
| `requires_restart` | `true` when any setting in the cluster has `activation_mode = restart` and a `configuration_reload` phase is emitted |

Rejected clusters emit no phase rows.

## Operation `phase_index`

Each `operation_rows` entry carries the `phase_index` of the phase that
contains it. Operations listed only as dependencies (for example
`connect_database` with no SQL statement) still receive the
`database_transaction` phase index when included in that phase's
`operation_ids`.

## SQL boundaries

- **Transactional phases** (`cluster_transaction`, `database_transaction`):
  emit `BEGIN;` … `COMMIT;` around phase statements.
- **Nontransactional phases** (`system_nontransactional`,
  `database_create_nontransactional`, `configuration_reload`): no transaction
  wrapper.
- **Database transaction phases**: emit `\connect <quoted-database-name>`
  immediately after the phase comment and before `BEGIN`.
- Never place `CREATE DATABASE` or `ALTER SYSTEM` inside `BEGIN`/`COMMIT`.
- Separate phases with exactly one blank line. No leading blank line. Exactly
  one trailing LF on the full SQL file.

## Phase rank for topological tie-break

When multiple operations are ready in the DAG, prefer lower phase rank, then
`cluster_id`, then `database_id_or_null` (null first), then operation-kind
rank, then `resource_id`, then `operation_id`. Phase ranks:
`cluster_transaction=0`, `system_nontransactional=1`,
`database_create_nontransactional=2`, `database_transaction=3`,
`configuration_reload=4`.

## Cluster require flags

`cluster_rows.requires_reload` is true when a `configuration_reload` phase is
emitted. `cluster_rows.requires_restart` is true when any resolved setting has
`activation_mode = restart`. Restart marks the cluster but does not emit a
restart SQL statement.
