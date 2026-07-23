# Operations catalog field notes

Catalog timestamps are UTC ISO-8601 strings whose lexical order is chronological. Effective intervals are closed. Disabled rows are historical only. Wildcard matching is represented by `*` in route-family rules, never by SQL NULL. Source epochs outrank advisory precedence ranks wherever the authority corpus names source-epoch precedence.

The batch interface is the sole catalog boundary. The recovery executable normally requests complete, ordered snapshots of `catalog_meta`, `deployment_context`, `site_alias`, `socket_policy`, `socket_candidate`, `body_tier`, `limit_candidate`, `limit_adjustment`, `timeout_band`, `auth_mode`, `route_family_rule`, `route_candidate`, `route_directive`, `route_dependency`, and `audit_rule`. The command emits SQL NULL as an empty field and replaces embedded tabs or newlines with spaces.

Route candidates carry `selection_class`: base rows enter initial method/path selection, replacement rows enter only through replace directives, and required rows enter only through require directives or dependency closure.
