// Package audit records security-relevant events (login attempts, admin
// actions) so operators can review them later.
package audit

import (
	"database/sql"
	"fmt"
)

// Record inserts an audit_log row for the given event and username. It
// never returns an error to the caller's request path failing outright;
// callers should log a failure to write an audit row rather than reject
// the request because of it.
func Record(conn *sql.DB, event, username string) error {
	if _, err := conn.Exec(`INSERT INTO audit_log (event, username) VALUES (?, ?)`, event, username); err != nil {
		return fmt.Errorf("record audit event: %w", err)
	}
	return nil
}

// Entry is a single row read back from audit_log, newest first.
type Entry struct {
	ID        int64
	Event     string
	Username  string
	CreatedAt string
}

// Recent returns the most recent audit_log entries, newest first, limited
// to limit rows.
func Recent(conn *sql.DB, limit int) ([]Entry, error) {
	rows, err := conn.Query(`SELECT id, event, username, created_at FROM audit_log ORDER BY id DESC LIMIT ?`, limit)
	if err != nil {
		return nil, fmt.Errorf("query audit log: %w", err)
	}
	defer rows.Close()

	var out []Entry
	for rows.Next() {
		var e Entry
		if err := rows.Scan(&e.ID, &e.Event, &e.Username, &e.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan audit log row: %w", err)
		}
		out = append(out, e)
	}
	return out, nil
}
