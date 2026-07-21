package main

import "time"

type Job struct {
	ID         int       `json:"id"`
	Type       string    `json:"type"`
	Payload    string    `json:"payload"`
	Status     string    `json:"status"`
	Priority   int       `json:"priority"`
	WorkerID   *int      `json:"worker_id"`
	WorkerName string    `json:"worker_name"`
	CreatedAt  time.Time `json:"created_at"`
	UpdatedAt  time.Time `json:"updated_at"`
}

type Worker struct {
	ID           int       `json:"id"`
	Name         string    `json:"name"`
	Status       string    `json:"status"`
	RegisteredAt time.Time `json:"registered_at"`
}

type QueueStats struct {
	Pending   int `json:"pending"`
	Running   int `json:"running"`
	Completed int `json:"completed"`
	Failed    int `json:"failed"`
	Cancelled int `json:"cancelled"`
}

type CreateJobRequest struct {
	Type     string `json:"type"`
	Payload  string `json:"payload"`
	Priority int    `json:"priority"`
}

type RegisterWorkerRequest struct {
	Name string `json:"name"`
}
