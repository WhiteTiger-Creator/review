package handlers

import "net/http"

// AdminUsers lists every account. Only callers resolved with role=admin
// may access it.
func (s *Server) AdminUsers(w http.ResponseWriter, r *http.Request) {
	id := s.resolveIdentity(r)
	if id == nil || id.Role != "admin" {
		writeError(w, http.StatusForbidden, "admin role required")
		return
	}
	rows, err := s.DB.Query(`SELECT id, username, role FROM users ORDER BY id`)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not list users")
		return
	}
	defer rows.Close()

	type userRow struct {
		ID       int64  `json:"id"`
		Username string `json:"username"`
		Role     string `json:"role"`
	}
	var out []userRow
	for rows.Next() {
		var u userRow
		if err := rows.Scan(&u.ID, &u.Username, &u.Role); err != nil {
			writeError(w, http.StatusInternalServerError, "could not read users")
			return
		}
		out = append(out, u)
	}
	writeJSON(w, http.StatusOK, map[string]interface{}{"users": out})
}

// AdminServiceToken mints an RS256 service token for internal
// integrations. Only admins may call it.
func (s *Server) AdminServiceToken(w http.ResponseWriter, r *http.Request) {
	id := s.resolveIdentity(r)
	if id == nil || id.Role != "admin" {
		writeError(w, http.StatusForbidden, "admin role required")
		return
	}
	token, err := s.Keys.IssueServiceToken("internal")
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not issue service token")
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"service_token": token})
}
