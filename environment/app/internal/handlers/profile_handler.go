package handlers

import "net/http"

// Profile returns the caller's own username/role.
func (s *Server) Profile(w http.ResponseWriter, r *http.Request) {
	id := s.resolveIdentity(r)
	if id == nil {
		writeError(w, http.StatusUnauthorized, "authentication required")
		return
	}
	var username string
	if err := s.DB.QueryRow(`SELECT username FROM users WHERE id = ?`, id.UserID).Scan(&username); err != nil {
		writeError(w, http.StatusInternalServerError, "could not load profile")
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"username": username, "role": id.Role})
}
