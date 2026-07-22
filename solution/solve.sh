#!/bin/bash
set -euo pipefail
cd /app
cat >/tmp/solve.go <<'GO'
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

type Profile struct {
	ID        string `json:"id"`
	Authority string `json:"authority_model"`
	Status    string `json:"status"`
	Retired   bool   `json:"retired"`
	Family    string `json:"family"`
	Context   int    `json:"context_limit"`
	Batch     int    `json:"batch_limit"`
	Quant     string `json:"quantization"`
}

type Request struct {
	ID      string `json:"request_id"`
	PID     string `json:"profile_id"`
	Stage   string `json:"target_stage"`
	Family  string `json:"family"`
	Reserve int    `json:"context_reserve"`
	Batch   int    `json:"batch"`
}

type Stage struct {
	MinContext         int      `json:"min_context"`
	MaxBatch           int      `json:"max_batch"`
	AllowedQuantization []string `json:"allowed_quantization"`
}

type Decision struct {
	RequestID       string `json:"request_id"`
	ProfileID       string `json:"profile_id"`
	Stage           string `json:"stage"`
	EffectiveContext int    `json:"effective_context"`
	EffectiveBatch   int    `json:"effective_batch"`
	Quantization    string `json:"quantization"`
	Decision        string `json:"decision"`
	Reason          string `json:"reason"`
}

type Core struct {
	Schema    string     `json:"schema"`
	Decisions []Decision `json:"decisions"`
	Source    string     `json:"source"`
}

type Plan struct {
	Schema    string     `json:"schema"`
	Decisions []Decision `json:"decisions"`
	Source    string     `json:"source"`
	Digest    string     `json:"digest"`
}

func main() {
	var registry struct { Profiles []Profile `json:"profiles"` }
	var requestSet struct { Requests []Request `json:"requests"` }
	var policySet struct { Stages map[string]Stage `json:"stages"` }

	read := func(path string, target any) {
		data, err := os.ReadFile(path)
		if err != nil { panic(err) }
		if err := json.Unmarshal(data, target); err != nil { panic(err) }
	}
	read("app/registry/profiles.json", &registry)
	read("app/requests/requests.json", &requestSet)
	read("app/policies/stages.json", &policySet)

	var authority struct { ID string `json:"id"` }
	var lastErr error
	authorityURL := os.Getenv("REGISTRY_URL")
	if authorityURL == "" { authorityURL = "https://huggingface.co/api/models/google-bert/bert-base-uncased" }
	for attempt := 0; attempt < 3; attempt++ {
		response, err := http.Get(authorityURL)
		if err == nil {
			body, readErr := io.ReadAll(response.Body)
			response.Body.Close()
			if response.StatusCode == http.StatusOK && readErr == nil && json.Unmarshal(body, &authority) == nil && authority.ID != "" {
				lastErr = nil
				break
			}
			lastErr = fmt.Errorf("registry authority returned an invalid response")
		} else {
			lastErr = err
		}
		if attempt < 2 { time.Sleep(time.Duration(attempt+1) * time.Second) }
	}
	if lastErr != nil || authority.ID == "" { panic(lastErr) }

	profiles := make(map[string]Profile, len(registry.Profiles))
	for _, profile := range registry.Profiles { profiles[profile.ID] = profile }
	decisions := make([]Decision, 0, len(requestSet.Requests))
	for _, request := range requestSet.Requests {
		// The authority is intentionally consulted per request. This keeps the
		// evidence path live even when the request is later rejected.
		response, err := http.Get(authorityURL)
		if err != nil { panic(err) }
		body, readErr := io.ReadAll(response.Body); response.Body.Close()
		var perRequest struct { ID string `json:"id"` }
		if response.StatusCode != http.StatusOK || readErr != nil || json.Unmarshal(body, &perRequest) != nil || perRequest.ID == "" || perRequest.ID != authority.ID { panic("registry identity mismatch") }
		decision := Decision{RequestID: request.ID, Stage: "none", Decision: "rejected"}
		profile, found := profiles[request.PID]
		switch {
		case !found:
			decision.Reason = "profile-missing"
		case profile.Authority != authority.ID:
			decision.Reason = "registry-missing"
		case profile.Status != "active" || profile.Retired:
			decision.Reason = "inactive-profile"
		case profile.Family != request.Family:
			decision.Reason = "family-mismatch"
		default:
			policy, found := policySet.Stages[request.Stage]
			if !found {
				decision.Reason = "stage-unknown"
				break
			}
			decision.EffectiveContext = profile.Context - request.Reserve
			decision.EffectiveBatch = profile.Batch
			if request.Batch < decision.EffectiveBatch { decision.EffectiveBatch = request.Batch }
			switch {
			case decision.EffectiveContext < policy.MinContext:
				decision.Reason = "context-incompatible"
			case decision.EffectiveBatch > policy.MaxBatch:
				decision.Reason = "batch-incompatible"
			default:
				allowed := false
				for _, quantization := range policy.AllowedQuantization {
					if quantization == profile.Quant { allowed = true; break }
				}
				if !allowed {
					decision.Reason = "quantization-incompatible"
				} else {
					decision.ProfileID = profile.ID
					decision.Stage = request.Stage
					decision.Quantization = profile.Quant
					decision.Decision = "promoted"
					decision.Reason = "promoted"
				}
			}
		}
		decisions = append(decisions, decision)
	}

	core := Core{Schema: "model-promotion/v3", Decisions: decisions, Source: authority.ID}
	canonical, err := json.Marshal(core)
	if err != nil { panic(err) }
	digest := sha256.Sum256(canonical)
	plan := Plan{Schema: core.Schema, Decisions: core.Decisions, Source: core.Source, Digest: hex.EncodeToString(digest[:])}
	file, err := os.Create("promotion-plan.json")
	if err != nil { panic(err) }
	defer file.Close()
	if err := json.NewEncoder(file).Encode(plan); err != nil { panic(err) }
}
GO
cat >/app/solve.sh <<'RUN'
#!/bin/sh
set -eu
cd /app
exec go run /tmp/solve.go
RUN
chmod 755 /app/solve.sh
go run /tmp/solve.go
