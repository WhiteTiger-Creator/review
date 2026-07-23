package db

import (
	"database/sql"
	"fmt"

	"authgw/internal/auth"
)

// SeedAccount describes a fixture account created at startup if it does
// not already exist.
type SeedAccount struct {
	Username string
	Password string
	Role     string
}

// Seed ensures each account in accounts exists, hashing passwords with
// bcrypt on insert.
func Seed(conn *sql.DB, accounts []SeedAccount) error {
	for _, acc := range accounts {
		var count int
		if err := conn.QueryRow(`SELECT COUNT(*) FROM users WHERE username = ?`, acc.Username).Scan(&count); err != nil {
			return fmt.Errorf("check existing user %s: %w", acc.Username, err)
		}
		if count > 0 {
			continue
		}
		hash, err := auth.HashPassword(acc.Password)
		if err != nil {
			return fmt.Errorf("hash password for %s: %w", acc.Username, err)
		}
		if _, err := conn.Exec(`INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)`,
			acc.Username, hash, acc.Role); err != nil {
			return fmt.Errorf("insert user %s: %w", acc.Username, err)
		}
	}
	return nil
}
