package report

import (
	"crypto/sha256"
	"encoding/hex"
	"sort"
	"strings"

	"bsplan/pkg/plan"
)

type Summary struct {
	ScenariosTotal int    `json:"scenarios_total"`
	AllConverged   bool   `json:"all_converged"`
	ReportDigest   string `json:"report_digest"`
}

type File struct {
	SchemaVersion int                 `json:"schema_version"`
	Command       string              `json:"command"`
	Scenarios     []plan.ScenarioPlan `json:"scenarios"`
	Summary       Summary             `json:"summary"`
}

func Build(command string, scenarios []plan.ScenarioPlan) File {
	rows := append([]plan.ScenarioPlan{}, scenarios...)
	sort.Slice(rows, func(i, j int) bool { return rows[i].ScenarioID < rows[j].ScenarioID })
	allConverged := true
	lines := make([]string, 0, len(rows))
	for _, row := range rows {
		if !row.RootsReachable || !row.WithinBudget {
			allConverged = false
		}
		lines = append(lines, row.ScenarioID+"|"+row.InputDigest+"|"+row.PlanDigest)
	}
	sort.Strings(lines)
	hash := sha256.Sum256([]byte(strings.Join(lines, "\n")))
	return File{
		SchemaVersion: 2,
		Command:       command,
		Scenarios:     rows,
		Summary: Summary{
			ScenariosTotal: len(rows),
			AllConverged:   allConverged,
			ReportDigest:   hex.EncodeToString(hash[:]),
		},
	}
}
