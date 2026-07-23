// Command authgw is a small internal authentication gateway: it issues
// HS256 session tokens on password login, supports a "remember me" cookie
// fallback, and lets admins mint RS256 service tokens for internal
// integrations. Its public key is published at /.well-known/jwks.json.
package main

import (
	"log"
	"net/http"

	"authgw/internal/auth"
	"authgw/internal/config"
	"authgw/internal/db"
	"authgw/internal/handlers"
	"authgw/internal/httpmw"
)

func main() {
	cfg := config.Load()

	conn, err := db.Open(cfg.DBPath)
	if err != nil {
		log.Fatalf("open database: %v", err)
	}
	defer conn.Close()

	if err := db.Seed(conn, []db.SeedAccount{
		{Username: "admin", Password: "CorrectHorseBattery9", Role: "admin"},
		{Username: "demo", Password: "hunter2hunter2", Role: "user"},
	}); err != nil {
		log.Fatalf("seed database: %v", err)
	}

	keys, err := auth.NewKeys()
	if err != nil {
		log.Fatalf("generate signing keys: %v", err)
	}

	srv := &handlers.Server{DB: conn, Keys: keys}

	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", srv.Healthz)
	mux.HandleFunc("GET /.well-known/jwks.json", srv.JWKS)
	mux.HandleFunc("POST /auth/register", srv.Register)
	mux.HandleFunc("POST /auth/login", srv.Login)
	mux.HandleFunc("GET /api/profile", srv.Profile)
	mux.HandleFunc("GET /admin/users", srv.AdminUsers)
	mux.HandleFunc("POST /admin/service-tokens", srv.AdminServiceToken)
	mux.HandleFunc("GET /admin/audit-log", srv.AdminAuditLog)

	var handler http.Handler = mux
	handler = httpmw.SecurityHeaders(handler)
	handler = httpmw.Logging(handler)
	handler = httpmw.RequestID(handler)

	log.Printf("authgw listening on %s (db=%s)", cfg.Addr, cfg.DBPath)
	log.Fatal(http.ListenAndServe(cfg.Addr, handler))
}
