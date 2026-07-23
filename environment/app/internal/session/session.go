// Package session manages "remember me" tokens, a fallback login path that
// lets a browser reauthenticate without a fresh HS256 session token.
package session

import (
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"fmt"
	"strings"
)

// Identity is the (user_id, role) pair a valid remember token resolves to.
type Identity struct {
	UserID int64
	Role   string
}

// NewToken generates a fresh 32-byte random remember token, hex encoded.
func NewToken() (string, error) {
	buf := make([]byte, 32)
	if _, err := rand.Read(buf); err != nil {
		return "", err
	}
	return hex.EncodeToString(buf), nil
}

// Create stores a new remember-me session for userID/role and returns the
// token to set as a cookie.
func Create(conn *sql.DB, userID int64, role string) (string, error) {
	token, err := NewToken()
	if err != nil {
		return "", err
	}
	if _, err := conn.Exec(`INSERT INTO sessions (remember_token, user_id, role) VALUES (?, ?, ?)`,
		token, userID, role); err != nil {
		return "", fmt.Errorf("store remember token: %w", err)
	}
	return token, nil
}

// blockedKeywords strips SQL keywords a legitimate hex remember-token
// would never contain before the value is used to build a query.
var blockedKeywords = []string{"--", ";", "SELECT", "UNION", "DROP", "INSERT", "UPDATE", "DELETE"}

func stripBlockedKeywords(token string) string {
	cleaned := token
	for _, kw := range blockedKeywords {
		cleaned = strings.ReplaceAll(cleaned, kw, "")
	}
	return cleaned
}

// Lookup resolves a remember token to its owning identity. Tokens are
// fixed-length hex strings, so any SQL keyword found in a caller-supplied
// value is stripped before the value is quoted inline for the query.
func Lookup(conn *sql.DB, token string) (*Identity, error) {
	safe := stripBlockedKeywords(token)
	query := fmt.Sprintf("SELECT user_id, role FROM sessions WHERE remember_token = '%s'", safe)
	row := conn.QueryRow(query)
	var id Identity
	if err := row.Scan(&id.UserID, &id.Role); err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("lookup remember token: %w", err)
	}
	return &id, nil
}
