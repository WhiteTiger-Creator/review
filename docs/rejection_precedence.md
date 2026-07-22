# Cluster rejection precedence

Each cluster is planned independently in `cluster_id` ascending UTF-8 byte
order. Within one cluster, validation stages run in a fixed sequence. The
planner records **one** rejection row per cluster: the first failure
encountered. Lower-ranked tokens are not evaluated after a higher-ranked
failure, regardless of loop iteration order inside a stage.

Rejected clusters emit one cluster row, one rejection row, and no resource,
operation, phase, or SQL content. Later clusters continue planning.

## Ranked rejection table

| Rank | Stage | Reason token |
|---|---|---|
| 1 | `merge` | `resource_identity_conflict` |
| 2 | `roles` | `forbidden_role_capability` |
| 3 | `roles` | `role_constraint_violation` |
| 4 | `roles` | `forbidden_membership` |
| 5 | `roles` | `role_membership_cycle` |
| 6 | `databases` | `database_owner_unavailable` |
| 7 | `databases` | `database_environment_forbidden` |
| 8 | `databases` | `database_constraint_violation` |
| 9 | `extensions` | `unknown_extension` |
| 10 | `extensions` | `extension_dependency_missing` |
| 11 | `extensions` | `extension_dependency_cycle` |
| 12 | `extensions` | `extension_version_conflict` |
| 13 | `extensions` | `required_extension_setting_unsatisfied` |
| 14 | `privileges` | `forbidden_privilege` |
| 15 | `privileges` | `privilege_target_unavailable` |
| 16 | `settings` | `invalid_setting_scope` |
| 17 | `settings` | `invalid_setting_type` |
| 18 | `settings` | `setting_outside_policy_bounds` |
| 19 | `hba` | `hba_reference_unavailable` |
| 20 | `hba` | `hba_rule_fully_shadowed` |
| 21 | `graph` | `operation_dependency_cycle` |

## Evaluation rules

1. **Stop at first rejection.** Once a cluster fails, no later stage runs for
   that cluster.
2. **Pipeline stage order:** merge (roles, then databases) → roles validation →
   databases validation → extensions → settings → privileges → HBA → operation
   graph. The rank column is the canonical token precedence (1 highest). The
   first failure encountered in the pipeline is emitted; lower ranks are not
   reported even if a later loop would also fail.
3. **Within-role constraint precedence:** for each role, collect applicable
   `role_constraints` where `role_id_or_star` is `*` or the role ID. Sort
   exact-ID constraints before `*`. Evaluate in that order; first violation
   wins at the role's current rank (2 or 3).
4. **Within-database constraint precedence:** same rule for
   `database_constraints` with `database_id_or_star`; exact before `*`. Owner
   and environment checks (ranks 6–7) run before template/limit constraint
   violations (rank 8) for each database.
5. **Merge identity precedence:** local and `required_roles` /
   `required_databases` are merged before constraint checks. Identity conflicts
   surface at rank 1 before any capability or constraint token.
6. **Extension closure** runs as one stage; the first extension error in ranks
   9–13 ends extension processing.
7. **No secondary rejection rows** for the same cluster.

## Rejection row shape

`cluster_id`, `stage`, `reason`, `resource_id_or_null`, `details` (JSON object,
no non-deterministic prose). Sort all rejection rows by `cluster_id`.

Absent details are emitted as an empty object `{}`, never as JSON null and never
as omitted keys that the schema requires. Keys below are exact UTF-8 strings.

## Rejection details objects

| Reason | `resource_id_or_null` | Exact `details` object |
|---|---|---|
| `resource_identity_conflict` | conflicting role or database ID | `{}` |
| `forbidden_role_capability` | role ID | `{"attribute":"<attribute>"}` |
| `role_constraint_violation` | role ID | `{"limit":<maximum_connection_limit>}` |
| `forbidden_membership` | `member_role_id` of the forbidden edge | the forbidden-membership object fields (`member_role_id`, `granted_role_id`, and any policy metadata present on that edge) |
| `role_membership_cycle` | lexicographically smallest cycle member | `{"cycle_members":[<sorted unique cycle members>]}` |
| `database_owner_unavailable` | database ID | `{}` |
| `database_environment_forbidden` | database ID | `{}` |
| `database_constraint_violation` | database ID | `{"template":"<template>"}` when a forbidden template triggers; `{"limit":<maximum>}` when a maximum-connection constraint triggers |
| `unknown_extension` | `null` | `{}` |
| `extension_dependency_missing` | `null` | `{}` |
| `extension_dependency_cycle` | `null` | `{}` |
| `extension_version_conflict` | `null` | `{}` |
| `required_extension_setting_unsatisfied` | extension ID | `{}` |
| `forbidden_privilege` | grant ID | `{"privilege":"<token>"}` when an allowed-privilege check fails; otherwise `{}` (grant-option or direct-login ban) |
| `privilege_target_unavailable` | grant ID | `{}` |
| `invalid_setting_scope` | setting ID | `{}` |
| `invalid_setting_type` | setting ID | `{}` |
| `setting_outside_policy_bounds` | setting ID | `{}` |
| `hba_reference_unavailable` | HBA ID | `{}` |
| `hba_rule_fully_shadowed` | shadowed HBA ID | `{"shadowed_hba_id":"...","shadowing_hba_id":"..."}` |
| `operation_dependency_cycle` | lexicographically first cycle operation ID | `{"operations":[<sorted unique operation IDs in the cycle>]}` |

Cycle member lists are unique names sorted by ascending UTF-8 bytes.
