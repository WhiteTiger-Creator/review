CREATE TABLE IF NOT EXISTS migration_run (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  error TEXT
);

CREATE TABLE IF NOT EXISTS graph_edge (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  edge_key TEXT NOT NULL,
  source TEXT NOT NULL,
  target TEXT NOT NULL,
  environment TEXT NOT NULL,
  method TEXT NOT NULL,
  path TEXT NOT NULL,
  authz_scope TEXT NOT NULL,
  denied INTEGER NOT NULL DEFAULT 0,
  UNIQUE(run_id, edge_key)
);

CREATE TABLE IF NOT EXISTS discovery_snapshot (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  issuer TEXT NOT NULL,
  jwks_uri TEXT NOT NULL,
  fetch_url TEXT NOT NULL,
  semantic_url TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jwk_evidence (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  kid TEXT NOT NULL,
  kty TEXT NOT NULL,
  alg TEXT NOT NULL,
  issuer TEXT NOT NULL,
  UNIQUE(run_id, issuer, kid)
);

CREATE TABLE IF NOT EXISTS policy_edge (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  edge_key TEXT NOT NULL,
  action TEXT NOT NULL,
  issuer TEXT,
  audiences TEXT,
  algorithms TEXT,
  UNIQUE(run_id, edge_key)
);
