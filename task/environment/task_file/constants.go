package main

const (
	JobStatusPending   = "pending"
	JobStatusRunning   = "running"
	JobStatusCompleted = "completed"
	JobStatusFailed    = "failed"
	JobStatusCancelled = "cancelled"

	WorkerStatusIdle = "idle"
	WorkerStatusBusy = "busy"

	DefaultPort   = "8080"
	DefaultDBPath = "/opt/jobqueue/jobs.db"
	ConfigPath    = "/opt/jobqueue/worker_config.json"
)
