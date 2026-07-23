package handlers

import (
	"encoding/json"
	"net/http"

	"authgw/internal/audit"
	"authgw/internal/auth"
	"authgw/internal/session"
)

type registerRequest struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

// Register creates a new, non-admin user account.
func (s *Server) Register(w http.ResponseWriter, r *http.Request) {
	var req registerRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}
	if len(req.Username) < 3 || len(req.Password) < 8 {
		writeError(w, http.StatusBadRequest, "username must be >=3 chars and password >=8 chars")
		return
	}
	hash, err := auth.HashPassword(req.Password)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not hash password")
		return
	}
	if _, err := s.DB.Exec(`INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'user')`,
		req.Username, hash); err != nil {
		writeError(w, http.StatusConflict, "username already taken")
		return
	}
	writeJSON(w, http.StatusCreated, map[string]string{"status": "created"})
}

type loginRequest struct {
	Username string `json:"username"`
	Password string `json:"password"`
	Remember bool   `json:"remember"`
}

// Login verifies credentials and issues an HS256 session token. When
// Remember is set, it also creates a remember-me cookie.
func (s *Server) Login(w http.ResponseWriter, r *http.Request) {
	var req loginRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	var (
		id           int64
		passwordHash string
		role         string
	)
	err := s.DB.QueryRow(`SELECT id, password_hash, role FROM users WHERE username = ?`, req.Username).
		Scan(&id, &passwordHash, &role)
	if err != nil || !auth.CheckPassword(passwordHash, req.Password) {
		_ = audit.Record(s.DB, "login_failure", req.Username)
		writeError(w, http.StatusUnauthorized, "invalid username or password")
		return
	}
	_ = audit.Record(s.DB, "login_success", req.Username)

	token, err := s.Keys.IssueSessionToken(id, req.Username, role)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not issue token")
		return
	}

	resp := map[string]string{"token": token}
	if req.Remember {
		rememberToken, err := session.Create(s.DB, id, role)
		if err != nil {
			writeError(w, http.StatusInternalServerError, "could not create remember-me session")
			return
		}
		http.SetCookie(w, &http.Cookie{
			Name:     "remember_token",
			Value:    rememberToken,
			Path:     "/",
			HttpOnly: true,
		})
		resp["remember_token"] = rememberToken
	}
	writeJSON(w, http.StatusOK, resp)
}
