package cache

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"sort"
	"strings"

	"bsplan/pkg/plan"
)

type Entry struct {
	ScenarioID  string            `json:"scenario_id"`
	InputDigest string            `json:"input_digest"`
	Plan        plan.ScenarioPlan `json:"plan"`
}

type File struct {
	SchemaVersion int     `json:"schema_version"`
	Entries       []Entry `json:"entries"`
}

type Run struct {
	SchemaVersion int      `json:"schema_version"`
	Reused        []string `json:"reused"`
	Recomputed    []string `json:"recomputed"`
	Removed       []string `json:"removed"`
	CacheRebuilt  bool     `json:"cache_rebuilt"`
	CacheDigest   string   `json:"cache_digest"`
	ReportDigest  string   `json:"report_digest"`
}

func Read(path string) (map[string]Entry, bool) {
	raw, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return map[string]Entry{}, false
	}
	if err != nil {
		return map[string]Entry{}, true
	}
	var file File
	if err := json.Unmarshal(raw, &file); err != nil || file.SchemaVersion != 1 {
		return map[string]Entry{}, true
	}
	entries := map[string]Entry{}
	for _, entry := range file.Entries {
		if entry.ScenarioID == "" || len(entry.InputDigest) != 64 || entries[entry.ScenarioID].ScenarioID != "" {
			return map[string]Entry{}, true
		}
		if entry.Plan.ScenarioID != entry.ScenarioID || entry.Plan.InputDigest != entry.InputDigest {
			return map[string]Entry{}, true
		}
		if len(entry.Plan.PlanDigest) != 64 || plan.ComputePlanDigest(entry.Plan) != entry.Plan.PlanDigest {
			return map[string]Entry{}, true
		}
		entries[entry.ScenarioID] = entry
	}
	return entries, false
}

func Build(entries map[string]Entry) File {
	ids := make([]string, 0, len(entries))
	for id := range entries {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	file := File{SchemaVersion: 1, Entries: make([]Entry, 0, len(ids))}
	for _, id := range ids {
		file.Entries = append(file.Entries, entries[id])
	}
	return file
}

func Digest(file File) string {
	lines := make([]string, 0, len(file.Entries))
	for _, entry := range file.Entries {
		lines = append(lines, entry.ScenarioID+"|"+entry.InputDigest+"|"+entry.Plan.PlanDigest)
	}
	sort.Strings(lines)
	hash := sha256.Sum256([]byte(strings.Join(lines, "\n")))
	return hex.EncodeToString(hash[:])
}
