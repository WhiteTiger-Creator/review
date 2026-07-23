// Package handlers implements authgw's HTTP surface: registration, login,
// profile, admin, service-token issuance, and the JWKS discovery document.
package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"strings"

	"authgw/internal/auth"
	"authgw/internal/session"
)

// Server bundles the dependencies every handler needs.
type Server struct {
	DB   *sql.DB
	Keys *auth.Keys
}

func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func writeError(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"error": msg})
}

// identity is the resolved caller of a request, from either a bearer
// session token or a remember-me cookie.
type identity struct {
	UserID int64
	Role   string
}

// resolveIdentity inspects the Authorization header first, then falls back
// to the remember_token cookie.
func (s *Server) resolveIdentity(r *http.Request) *identity {
	if h := r.Header.Get("Authorization"); strings.HasPrefix(h, "Bearer ") {
		raw := strings.TrimPrefix(h, "Bearer ")
		claims, err := s.Keys.ParseSessionToken(raw)
		if err == nil {
			return &identity{UserID: claims.UserID, Role: claims.Role}
		}
	}
	if c, err := r.Cookie("remember_token"); err == nil {
		id, err := session.Lookup(s.DB, c.Value)
		if err == nil && id != nil {
			return &identity{UserID: id.UserID, Role: id.Role}
		}
	}
	return nil
}
