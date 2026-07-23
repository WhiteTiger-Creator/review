package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"

	_ "modernc.org/sqlite"

	"authgw/internal/auth"
)

func newTestServer(t *testing.T) *Server {
	t.Helper()
	path := filepath.Join(t.TempDir(), "handlers_test.db")
	conn, err := sql.Open("sqlite", "file:"+path)
	if err != nil {
		t.Fatalf("open db: %v", err)
	}
	if _, err := conn.Exec(`CREATE TABLE users (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		username TEXT UNIQUE NOT NULL,
		password_hash TEXT NOT NULL,
		role TEXT NOT NULL DEFAULT 'user'
	);
	CREATE TABLE sessions (
		remember_token TEXT PRIMARY KEY,
		user_id INTEGER NOT NULL,
		role TEXT NOT NULL
	);`); err != nil {
		t.Fatalf("create schema: %v", err)
	}
	t.Cleanup(func() { conn.Close() })

	keys, err := auth.NewKeys()
	if err != nil {
		t.Fatalf("NewKeys: %v", err)
	}
	return &Server{DB: conn, Keys: keys}
}

func TestHealthz(t *testing.T) {
	s := newTestServer(t)
	rec := httptest.NewRecorder()
	s.Healthz(rec, httptest.NewRequest(http.MethodGet, "/healthz", nil))

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d", rec.Code, http.StatusOK)
	}
	var body map[string]string
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode body: %v", err)
	}
	if body["status"] != "ok" {
		t.Errorf("status field = %q, want %q", body["status"], "ok")
	}
}

func TestRegisterRejectsShortCredentials(t *testing.T) {
	s := newTestServer(t)
	body := strings.NewReader(`{"username":"ab","password":"short"}`)
	rec := httptest.NewRecorder()
	s.Register(rec, httptest.NewRequest(http.MethodPost, "/auth/register", body))

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want %d", rec.Code, http.StatusBadRequest)
	}
}

func TestRegisterThenLoginSucceeds(t *testing.T) {
	s := newTestServer(t)

	regRec := httptest.NewRecorder()
	s.Register(regRec, httptest.NewRequest(http.MethodPost, "/auth/register",
		strings.NewReader(`{"username":"carol","password":"correcthorsebattery"}`)))
	if regRec.Code != http.StatusCreated {
		t.Fatalf("register status = %d, want %d", regRec.Code, http.StatusCreated)
	}

	loginRec := httptest.NewRecorder()
	s.Login(loginRec, httptest.NewRequest(http.MethodPost, "/auth/login",
		strings.NewReader(`{"username":"carol","password":"correcthorsebattery"}`)))
	if loginRec.Code != http.StatusOK {
		t.Fatalf("login status = %d, want %d", loginRec.Code, http.StatusOK)
	}

	var body map[string]string
	if err := json.NewDecoder(loginRec.Body).Decode(&body); err != nil {
		t.Fatalf("decode body: %v", err)
	}
	if body["token"] == "" {
		t.Error("login response did not include a token")
	}
}

func TestAdminUsersRejectsUnauthenticated(t *testing.T) {
	s := newTestServer(t)
	rec := httptest.NewRecorder()
	s.AdminUsers(rec, httptest.NewRequest(http.MethodGet, "/admin/users", nil))

	if rec.Code != http.StatusForbidden {
		t.Fatalf("status = %d, want %d", rec.Code, http.StatusForbidden)
	}
}
