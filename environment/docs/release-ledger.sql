PRAGMA foreign_keys = ON;

CREATE TABLE release_run (
    run_id TEXT PRIMARY KEY,
    resolved_at TEXT NOT NULL,
    rust_version TEXT NOT NULL,
    cargo_version TEXT NOT NULL,
    cargo_audit_version TEXT NOT NULL,
    cargo_deny_version TEXT NOT NULL,
    cargo_lock_sha256 TEXT NOT NULL,
    rustsec_commit TEXT NOT NULL,
    offline_replay INTEGER NOT NULL CHECK (offline_replay IN (0, 1)),
    source_unchanged INTEGER NOT NULL CHECK (source_unchanged IN (0, 1))
);

CREATE TABLE dependency_change (
    run_id TEXT NOT NULL REFERENCES release_run(run_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    from_version TEXT NOT NULL,
    to_version TEXT NOT NULL,
    advisory_id TEXT NOT NULL,
    yanked_before INTEGER NOT NULL CHECK (yanked_before IN (0, 1)),
    target_rust_version TEXT NOT NULL,
    PRIMARY KEY (run_id, name)
);

CREATE TABLE policy_check (
    run_id TEXT NOT NULL REFERENCES release_run(run_id) ON DELETE CASCADE,
    tool TEXT NOT NULL,
    command TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status = 'pass'),
    PRIMARY KEY (run_id, tool)
);
