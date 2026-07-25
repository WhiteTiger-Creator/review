PRAGMA journal_mode=DELETE;
PRAGMA foreign_keys=ON;

CREATE TABLE catalog_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE deployment_context (
  site_key TEXT PRIMARY KEY,
  enabled INTEGER NOT NULL CHECK (enabled IN (0,1)),
  custody_code TEXT NOT NULL,
  platform_code TEXT NOT NULL,
  transport_code TEXT NOT NULL,
  incident_code TEXT NOT NULL,
  service_account TEXT NOT NULL,
  service_group TEXT NOT NULL,
  generation INTEGER NOT NULL CHECK (generation > 0),
  recovery_epoch TEXT NOT NULL,
  root_class TEXT NOT NULL,
  route_cohort TEXT NOT NULL,
  policy_epoch TEXT NOT NULL
);

CREATE TABLE site_alias (
  alias TEXT NOT NULL,
  site_key TEXT NOT NULL REFERENCES deployment_context(site_key),
  effective_from TEXT NOT NULL,
  effective_to TEXT NOT NULL,
  precedence_rank INTEGER NOT NULL,
  disabled INTEGER NOT NULL CHECK (disabled IN (0,1)),
  PRIMARY KEY(alias, site_key, effective_from)
);

CREATE TABLE socket_policy (
  root_class TEXT NOT NULL,
  transport_code TEXT NOT NULL,
  namespace_code TEXT NOT NULL,
  purpose_code TEXT NOT NULL,
  ownership_code TEXT NOT NULL,
  allowed INTEGER NOT NULL CHECK (allowed IN (0,1)),
  PRIMARY KEY(root_class, transport_code, namespace_code, purpose_code, ownership_code)
);

CREATE TABLE socket_candidate (
  candidate_id TEXT PRIMARY KEY,
  site_key TEXT NOT NULL REFERENCES deployment_context(site_key),
  path_template TEXT NOT NULL,
  namespace_code TEXT NOT NULL,
  purpose_code TEXT NOT NULL,
  ownership_code TEXT NOT NULL,
  mode_text TEXT NOT NULL,
  evidence_token TEXT NOT NULL,
  priority_bias INTEGER NOT NULL,
  effective_from TEXT NOT NULL,
  effective_to TEXT NOT NULL,
  disabled INTEGER NOT NULL CHECK (disabled IN (0,1))
);

CREATE TABLE body_tier (
  tier_code TEXT PRIMARY KEY,
  bytes_limit INTEGER NOT NULL CHECK (bytes_limit > 0),
  ordinal INTEGER NOT NULL UNIQUE
);

CREATE TABLE limit_candidate (
  profile_id TEXT PRIMARY KEY,
  site_key TEXT NOT NULL REFERENCES deployment_context(site_key),
  custody_code TEXT NOT NULL,
  platform_code TEXT NOT NULL,
  incident_code TEXT NOT NULL,
  fd_soft INTEGER NOT NULL CHECK (fd_soft > 0),
  reserve_fds INTEGER NOT NULL CHECK (reserve_fds >= 0),
  worker_cost INTEGER NOT NULL CHECK (worker_cost > 0),
  route_cost INTEGER NOT NULL CHECK (route_cost >= 0),
  listener_cost INTEGER NOT NULL CHECK (listener_cost >= 0),
  audit_cost INTEGER NOT NULL CHECK (audit_cost >= 0),
  backlog_floor INTEGER NOT NULL CHECK (backlog_floor > 0),
  backlog_cap INTEGER NOT NULL CHECK (backlog_cap >= backlog_floor),
  minimum_body_tier TEXT NOT NULL REFERENCES body_tier(tier_code),
  headroom_num INTEGER NOT NULL CHECK (headroom_num > 0),
  headroom_den INTEGER NOT NULL CHECK (headroom_den > 0),
  precedence_rank INTEGER NOT NULL,
  effective_from TEXT NOT NULL,
  effective_to TEXT NOT NULL,
  disabled INTEGER NOT NULL CHECK (disabled IN (0,1))
);

CREATE TABLE limit_adjustment (
  adjustment_id TEXT PRIMARY KEY,
  site_key TEXT NOT NULL REFERENCES deployment_context(site_key),
  trigger_code TEXT NOT NULL,
  add_reserve_fds INTEGER NOT NULL,
  add_route_cost INTEGER NOT NULL,
  add_body_bytes INTEGER NOT NULL,
  precedence_rank INTEGER NOT NULL,
  effective_from TEXT NOT NULL,
  effective_to TEXT NOT NULL,
  disabled INTEGER NOT NULL CHECK (disabled IN (0,1))
);

CREATE TABLE timeout_band (
  code TEXT PRIMARY KEY,
  milliseconds INTEGER NOT NULL CHECK (milliseconds > 0)
);

CREATE TABLE auth_mode (
  code TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE route_family_rule (
  rule_id TEXT PRIMARY KEY,
  custody_code TEXT NOT NULL,
  platform_code TEXT NOT NULL,
  transport_code TEXT NOT NULL,
  incident_code TEXT NOT NULL,
  request_segment TEXT NOT NULL,
  replay_mode TEXT NOT NULL,
  family_code TEXT NOT NULL,
  specificity INTEGER NOT NULL,
  source_epoch TEXT NOT NULL,
  precedence_rank INTEGER NOT NULL,
  effective_from TEXT NOT NULL,
  effective_to TEXT NOT NULL,
  disabled INTEGER NOT NULL CHECK (disabled IN (0,1))
);

CREATE TABLE route_candidate (
  route_id TEXT PRIMARY KEY,
  site_key TEXT NOT NULL REFERENCES deployment_context(site_key),
  family_code TEXT NOT NULL,
  cohort_code TEXT NOT NULL,
  selection_class TEXT NOT NULL CHECK (selection_class IN ('base','replacement','required')),
  method TEXT NOT NULL,
  external_path TEXT NOT NULL,
  upstream TEXT NOT NULL,
  auth_code TEXT NOT NULL REFERENCES auth_mode(code),
  timeout_code TEXT NOT NULL REFERENCES timeout_band(code),
  active INTEGER NOT NULL CHECK (active IN (0,1)),
  effective_from TEXT NOT NULL,
  effective_to TEXT NOT NULL,
  source_epoch TEXT NOT NULL,
  precedence_rank INTEGER NOT NULL
);

CREATE TABLE route_directive (
  directive_id TEXT PRIMARY KEY,
  site_key TEXT NOT NULL REFERENCES deployment_context(site_key),
  family_code TEXT NOT NULL,
  directive_kind TEXT NOT NULL CHECK (directive_kind IN ('withdraw','replace','require')),
  target_route_id TEXT NOT NULL,
  replacement_route_id TEXT,
  source_epoch TEXT NOT NULL,
  precedence_rank INTEGER NOT NULL,
  effective_from TEXT NOT NULL,
  effective_to TEXT NOT NULL,
  disabled INTEGER NOT NULL CHECK (disabled IN (0,1))
);

CREATE TABLE route_dependency (
  route_id TEXT NOT NULL REFERENCES route_candidate(route_id),
  required_route_id TEXT NOT NULL REFERENCES route_candidate(route_id),
  PRIMARY KEY(route_id, required_route_id)
);

CREATE TABLE audit_rule (
  name TEXT PRIMARY KEY,
  rule_ref TEXT NOT NULL,
  expected_class TEXT NOT NULL,
  ordinal INTEGER NOT NULL UNIQUE
);
