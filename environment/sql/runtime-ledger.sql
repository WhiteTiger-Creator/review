PRAGMA foreign_keys = ON;

CREATE TABLE runtime_runs (
    run_id TEXT PRIMARY KEY
);

CREATE TABLE runtime_changes (
    run_id TEXT NOT NULL REFERENCES runtime_runs(run_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    previous_version TEXT NOT NULL,
    selected_version TEXT NOT NULL,
    reason TEXT NOT NULL,
    PRIMARY KEY (run_id, name)
);
