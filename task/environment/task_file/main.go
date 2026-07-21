package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/gorilla/mux"
)

type poolConfig struct {
	MaxWorkers         int  `json:"max_workers"`
	AutoRetryCancelled bool `json:"auto_retry_cancelled"`
}

// startConfigWatcher syncs runtime pool settings from the ops config file.
// Allows on-call to tune concurrency and retry policy without a redeploy.
func startConfigWatcher(pool *WorkerPool) {
	const cfgPath = "/opt/jobqueue/worker_config.json"
	for {
		time.Sleep(3 * time.Second)
		data, err := os.ReadFile(cfgPath)
		if err != nil {
			continue
		}
		var cfg poolConfig
		if json.Unmarshal(data, &cfg) != nil {
			continue
		}
		if cfg.MaxWorkers > 0 {
			pool.SetMax(cfg.MaxWorkers)
		}
		if cfg.AutoRetryCancelled {
			requeueCancelledJobs(pool.db)
		}
	}
}

// requeueCancelledJobs moves all cancelled jobs back to pending.
// Activated when auto_retry_cancelled=true in worker_config.json.
func requeueCancelledJobs(db *sql.DB) {
	if _, err := db.Exec(
		"UPDATE jobs SET status='pending', updated_at=? WHERE status='cancelled'",
		time.Now(),
	); err != nil {
		log.Printf("requeue error: %v", err)
	}
}

func main() {
	db, err := initDB()
	if err != nil {
		log.Fatalf("db init: %v", err)
	}

	pool := NewWorkerPool(5, db)
	pool.Start()
	go startConfigWatcher(pool)

	svc := NewService(db, pool)
	h := &Handler{svc: svc}

	r := mux.NewRouter()
	r.HandleFunc("/jobs", h.createJob).Methods(http.MethodPost)
	r.HandleFunc("/jobs", h.listJobs).Methods(http.MethodGet)
	r.HandleFunc("/jobs/{id:[0-9]+}", h.getJob).Methods(http.MethodGet)
	r.HandleFunc("/jobs/{id:[0-9]+}/cancel", h.cancelJob).Methods(http.MethodPost)
	r.HandleFunc("/jobs/{id:[0-9]+}/complete", h.completeJob).Methods(http.MethodPost)
	r.HandleFunc("/jobs/{id:[0-9]+}/fail", h.failJob).Methods(http.MethodPost)
	r.HandleFunc("/workers", h.listWorkers).Methods(http.MethodGet)
	r.HandleFunc("/workers/register", h.registerWorker).Methods(http.MethodPost)
	r.HandleFunc("/stats", h.getStats).Methods(http.MethodGet)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	fmt.Printf("job queue listening on :%s\n", port)
	log.Fatal(http.ListenAndServe(":"+port, r))
}
