package handlers

import "net/http"

// Healthz is a liveness probe. It reports this replica's instance ID so
// operators running multiple replicas can tell which one answered.
func (s *Server) Healthz(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{
		"status":      "ok",
		"instance_id": s.Keys.InstanceID,
	})
}
