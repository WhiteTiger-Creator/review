package main

import (
	"database/sql"
	"fmt"
	"os"

	_ "github.com/mattn/go-sqlite3"
)

const schema = `
CREATE TABLE IF NOT EXISTS workers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL UNIQUE,
    status        TEXT    NOT NULL DEFAULT 'idle',
    registered_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS jobs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    type       TEXT    NOT NULL,
    payload    TEXT    NOT NULL DEFAULT '',
    status     TEXT    NOT NULL DEFAULT 'pending',
    priority   INTEGER NOT NULL DEFAULT 0,
    worker_id  INTEGER REFERENCES workers(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
`

func initDB() (*sql.DB, error) {
	dbPath := os.Getenv("DB_PATH")
	if dbPath == "" {
		dbPath = "/opt/jobqueue/jobs.db"
	}

	db, err := sql.Open("sqlite3", dbPath+"?_journal_mode=WAL")
	if err != nil {
		return nil, fmt.Errorf("open: %w", err)
	}
	db.SetMaxOpenConns(1)

	if _, err := db.Exec(schema); err != nil {
		return nil, fmt.Errorf("schema: %w", err)
	}

	if err := seedDB(db); err != nil {
		return nil, fmt.Errorf("seed: %w", err)
	}

	return db, nil
}

func seedDB(db *sql.DB) error {
	var count int
	if err := db.QueryRow("SELECT COUNT(*) FROM workers").Scan(&count); err != nil || count > 0 {
		return nil
	}

	for _, name := range []string{"worker-alpha", "worker-beta", "worker-gamma"} {
		if _, err := db.Exec("INSERT INTO workers (name) VALUES (?)", name); err != nil {
			return err
		}
	}

	w1, w2 := 1, 2
	type seedJob struct {
		jtype    string
		payload  string
		status   string
		priority int
		workerID *int
	}
	jobs := []seedJob{
		{"email", `{"to":"alice@corp.io","subject":"Welcome aboard"}`, "completed", 5, &w1},
		{"report", `{"report_id":"q4-2024","format":"pdf"}`, "running", 3, &w2},
		{"image_resize", `{"src":"/uploads/banner.png","width":1200}`, "pending", 0, nil},
		{"email", `{"to":"bob@corp.io","subject":"Your invoice is ready"}`, "pending", 2, nil},
		{"data_export", `{"table":"orders","since":"2024-01-01"}`, "failed", 1, &w1},
		{"notification", `{"user_id":99,"channel":"slack","msg":"Deploy done"}`, "pending", 4, nil},
	}
	for _, j := range jobs {
		if _, err := db.Exec(
			"INSERT INTO jobs (type, payload, status, priority, worker_id) VALUES (?,?,?,?,?)",
			j.jtype, j.payload, j.status, j.priority, j.workerID,
		); err != nil {
			return err
		}
	}
	return nil
}
