PRAGMA journal_mode=DELETE;
PRAGMA foreign_keys=ON;

CREATE TABLE schedule_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE maintenance_order (
  order_id TEXT PRIMARY KEY,
  site_alias TEXT NOT NULL,
  service_class TEXT NOT NULL,
  family_code TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('SCHEDULED','HOLD','CANCELLED')),
  not_before TEXT NOT NULL,
  not_after TEXT NOT NULL,
  source_epoch TEXT NOT NULL,
  precedence_rank INTEGER NOT NULL,
  ack_weight_required INTEGER NOT NULL CHECK (ack_weight_required > 0),
  disabled INTEGER NOT NULL CHECK (disabled IN (0,1))
);

CREATE TABLE ack_role (
  role_code TEXT PRIMARY KEY,
  ack_weight INTEGER NOT NULL CHECK (ack_weight > 0),
  work_group TEXT NOT NULL
);

CREATE TABLE ack_event (
  event_id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL REFERENCES maintenance_order(order_id),
  operator_id TEXT NOT NULL,
  role_code TEXT NOT NULL REFERENCES ack_role(role_code),
  event_kind TEXT NOT NULL CHECK (event_kind IN ('acknowledge','withdraw','restore')),
  event_epoch TEXT NOT NULL,
  precedence_rank INTEGER NOT NULL
);

CREATE TABLE service_slot (
  slot_id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL REFERENCES maintenance_order(order_id),
  socket_candidate_id TEXT NOT NULL,
  body_tier_code TEXT NOT NULL,
  service_lane TEXT NOT NULL,
  source_epoch TEXT NOT NULL,
  precedence_rank INTEGER NOT NULL,
  effective_from TEXT NOT NULL,
  effective_to TEXT NOT NULL,
  disabled INTEGER NOT NULL CHECK (disabled IN (0,1))
);

CREATE TABLE schedule_rule (
  name TEXT PRIMARY KEY,
  rule_ref TEXT NOT NULL,
  expected_class TEXT NOT NULL,
  ordinal INTEGER NOT NULL UNIQUE
);
