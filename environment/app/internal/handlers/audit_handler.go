package handlers

import (
	"net/http"

	"authgw/internal/audit"
)

// AdminAuditLog returns the most recent audit log entries. Only callers
// resolved with role=admin may access it.
func (s *Server) AdminAuditLog(w http.ResponseWriter, r *http.Request) {
	id := s.resolveIdentity(r)
	if id == nil || id.Role != "admin" {
		writeError(w, http.StatusForbidden, "admin role required")
		return
	}
	entries, err := audit.Recent(s.DB, 50)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not read audit log")
		return
	}
	writeJSON(w, http.StatusOK, map[string]interface{}{"entries": entries})
}
