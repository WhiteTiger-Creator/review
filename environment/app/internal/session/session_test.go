package session

import (
	"database/sql"
	"path/filepath"
	"testing"

	_ "modernc.org/sqlite"
)

func openTestDB(t *testing.T) *sql.DB {
	t.Helper()
	path := filepath.Join(t.TempDir(), "session_test.db")
	conn, err := sql.Open("sqlite", "file:"+path)
	if err != nil {
		t.Fatalf("open db: %v", err)
	}
	if _, err := conn.Exec(`CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT);
		CREATE TABLE sessions (remember_token TEXT PRIMARY KEY, user_id INTEGER, role TEXT);`); err != nil {
		t.Fatalf("create schema: %v", err)
	}
	t.Cleanup(func() { conn.Close() })
	return conn
}

func TestNewTokenIsUniqueAndHex(t *testing.T) {
	a, err := NewToken()
	if err != nil {
		t.Fatalf("NewToken: %v", err)
	}
	b, err := NewToken()
	if err != nil {
		t.Fatalf("NewToken: %v", err)
	}
	if a == b {
		t.Fatalf("NewToken returned the same value twice: %s", a)
	}
	if len(a) != 64 {
		t.Errorf("len(token) = %d, want 64 (32 bytes hex-encoded)", len(a))
	}
}

func TestCreateAndLookupRoundTrip(t *testing.T) {
	conn := openTestDB(t)

	token, err := Create(conn, 42, "user")
	if err != nil {
		t.Fatalf("Create: %v", err)
	}

	id, err := Lookup(conn, token)
	if err != nil {
		t.Fatalf("Lookup: %v", err)
	}
	if id == nil {
		t.Fatal("Lookup returned nil for a token that was just created")
	}
	if id.UserID != 42 || id.Role != "user" {
		t.Errorf("Lookup = %+v, want UserID=42 Role=user", id)
	}
}

func TestLookupUnknownTokenReturnsNil(t *testing.T) {
	conn := openTestDB(t)

	id, err := Lookup(conn, "does-not-exist")
	if err != nil {
		t.Fatalf("Lookup: %v", err)
	}
	if id != nil {
		t.Errorf("Lookup(unknown) = %+v, want nil", id)
	}
}
