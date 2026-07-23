package audit

import (
	"database/sql"
	"path/filepath"
	"testing"

	_ "modernc.org/sqlite"
)

func openTestDB(t *testing.T) *sql.DB {
	t.Helper()
	path := filepath.Join(t.TempDir(), "audit_test.db")
	conn, err := sql.Open("sqlite", "file:"+path)
	if err != nil {
		t.Fatalf("open db: %v", err)
	}
	if _, err := conn.Exec(`CREATE TABLE audit_log (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		event TEXT NOT NULL,
		username TEXT NOT NULL,
		created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
	);`); err != nil {
		t.Fatalf("create schema: %v", err)
	}
	t.Cleanup(func() { conn.Close() })
	return conn
}

func TestRecordAndRecent(t *testing.T) {
	conn := openTestDB(t)

	if err := Record(conn, "login_success", "alice"); err != nil {
		t.Fatalf("Record: %v", err)
	}
	if err := Record(conn, "login_failure", "bob"); err != nil {
		t.Fatalf("Record: %v", err)
	}

	entries, err := Recent(conn, 10)
	if err != nil {
		t.Fatalf("Recent: %v", err)
	}
	if len(entries) != 2 {
		t.Fatalf("len(entries) = %d, want 2", len(entries))
	}
	// Recent() orders newest first.
	if entries[0].Event != "login_failure" || entries[0].Username != "bob" {
		t.Errorf("entries[0] = %+v, want event=login_failure username=bob", entries[0])
	}
	if entries[1].Event != "login_success" || entries[1].Username != "alice" {
		t.Errorf("entries[1] = %+v, want event=login_success username=alice", entries[1])
	}
}

func TestRecentRespectsLimit(t *testing.T) {
	conn := openTestDB(t)

	for i := 0; i < 5; i++ {
		if err := Record(conn, "login_success", "alice"); err != nil {
			t.Fatalf("Record: %v", err)
		}
	}

	entries, err := Recent(conn, 3)
	if err != nil {
		t.Fatalf("Recent: %v", err)
	}
	if len(entries) != 3 {
		t.Errorf("len(entries) = %d, want 3", len(entries))
	}
}
