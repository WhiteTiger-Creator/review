PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS compose_exceptions;
DROP TABLE IF EXISTS release_refs;
DROP TABLE IF EXISTS changelog_tags;
DROP TABLE IF EXISTS audit_events;
DROP TABLE IF EXISTS candidate_exception_reviews;
DROP TABLE IF EXISTS candidate_release_refs;
DROP TABLE IF EXISTS candidate_changelog_tags;

CREATE TABLE candidate_exception_reviews (
  exception_id TEXT NOT NULL,
  review_round INTEGER NOT NULL,
  status TEXT NOT NULL,
  service TEXT NOT NULL,
  compose_file TEXT NOT NULL,
  rule_code TEXT NOT NULL,
  expires_on TEXT,
  approver TEXT,
  evidence_ref TEXT,
  mount_target TEXT,
  secret_readonly INTEGER DEFAULT 0,
  environment TEXT NOT NULL DEFAULT 'prod',
  PRIMARY KEY (exception_id, review_round)
);

CREATE TABLE candidate_release_refs (
  ref_name TEXT PRIMARY KEY,
  source_url TEXT NOT NULL,
  observed_at TEXT NOT NULL
);

CREATE TABLE candidate_changelog_tags (
  tag_name TEXT PRIMARY KEY,
  source_url TEXT NOT NULL,
  signed INTEGER NOT NULL DEFAULT 0,
  changelog_entry TEXT NOT NULL DEFAULT '',
  observed_at TEXT NOT NULL
);

CREATE TABLE compose_exceptions (
  exception_id TEXT PRIMARY KEY,
  service TEXT NOT NULL,
  compose_file TEXT NOT NULL,
  rule_code TEXT NOT NULL,
  expires_on TEXT NOT NULL,
  approver TEXT NOT NULL,
  evidence_ref TEXT NOT NULL,
  mount_target TEXT NOT NULL DEFAULT '',
  environment TEXT NOT NULL,
  canonical_note TEXT NOT NULL
);

CREATE TABLE release_refs (
  branch TEXT PRIMARY KEY,
  source_ref TEXT NOT NULL,
  observed_at TEXT NOT NULL
);

CREATE TABLE changelog_tags (
  tag TEXT PRIMARY KEY,
  source_ref TEXT NOT NULL,
  signed INTEGER NOT NULL,
  observed_at TEXT NOT NULL
);

CREATE TABLE audit_events (
  event_key TEXT PRIMARY KEY,
  event_value TEXT NOT NULL
);
