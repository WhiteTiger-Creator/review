PRAGMA journal_mode=DELETE;
PRAGMA foreign_keys=ON;

CREATE TABLE change_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE change_ticket (
  ticket_id TEXT PRIMARY KEY,
  site_alias TEXT NOT NULL,
  incident_code TEXT NOT NULL,
  family_code TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('APPROVED','HOLD','CANCELLED')),
  not_before TEXT NOT NULL,
  not_after TEXT NOT NULL,
  source_epoch TEXT NOT NULL,
  precedence_rank INTEGER NOT NULL,
  quorum_required INTEGER NOT NULL CHECK (quorum_required > 0),
  disabled INTEGER NOT NULL CHECK (disabled IN (0,1))
);

CREATE TABLE approval_role (
  role_code TEXT PRIMARY KEY,
  quorum_weight INTEGER NOT NULL CHECK (quorum_weight > 0),
  exclusive_group TEXT NOT NULL
);

CREATE TABLE approval_event (
  event_id TEXT PRIMARY KEY,
  ticket_id TEXT NOT NULL REFERENCES change_ticket(ticket_id),
  approver_id TEXT NOT NULL,
  role_code TEXT NOT NULL REFERENCES approval_role(role_code),
  event_kind TEXT NOT NULL CHECK (event_kind IN ('approve','revoke','reinstate')),
  event_epoch TEXT NOT NULL,
  precedence_rank INTEGER NOT NULL
);

CREATE TABLE activation_candidate (
  activation_id TEXT PRIMARY KEY,
  ticket_id TEXT NOT NULL REFERENCES change_ticket(ticket_id),
  socket_candidate_id TEXT NOT NULL,
  body_tier_code TEXT NOT NULL,
  release_lane TEXT NOT NULL,
  source_epoch TEXT NOT NULL,
  precedence_rank INTEGER NOT NULL,
  effective_from TEXT NOT NULL,
  effective_to TEXT NOT NULL,
  disabled INTEGER NOT NULL CHECK (disabled IN (0,1))
);

CREATE TABLE authorization_rule (
  name TEXT PRIMARY KEY,
  rule_ref TEXT NOT NULL,
  expected_class TEXT NOT NULL,
  ordinal INTEGER NOT NULL UNIQUE
);
