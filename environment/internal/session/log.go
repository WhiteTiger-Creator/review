package session

import (
	"encoding/json"
	"os"
	"path/filepath"

	"hanabi/internal/rules"
	"hanabi/internal/scoring"
	"hanabi/internal/table"
)

// SessionLog is the per-scenario output document.
type SessionLog struct {
	Scenario        string         `json:"scenario"`
	MovesApplied    []int          `json:"moves_applied"`
	MovesRejected   []int          `json:"moves_rejected"`
	FinalInfoTokens int            `json:"final_info_tokens"`
	FinalFuseTokens int            `json:"final_fuse_tokens"`
	Fireworks       map[string]int `json:"fireworks"`
	Score           int            `json:"score"`
	GameOver        bool           `json:"game_over"`
	EndReason       string         `json:"end_reason"`
	HintsGiven      int            `json:"hints_given"`
	CardsPlayed     int            `json:"cards_played"`
	CardsDiscarded  int            `json:"cards_discarded"`
	PlyCount        int            `json:"ply_count"`
	FinalPlayer     int            `json:"final_player"`
}

// Summary aggregates totals across scenarios.
type Summary struct {
	ScenarioCount int            `json:"scenario_count"`
	TotalScore    int            `json:"total_score"`
	TotalHints    int            `json:"total_hints"`
	TotalPlays    int            `json:"total_plays"`
	TotalDiscards int            `json:"total_discards"`
	TotalPlies    int            `json:"total_plies"`
	EndReasons    map[string]int `json:"end_reasons"`
}

// FinalizeScore applies scoring policy, then runs scoreboard reconciliation.
func FinalizeScore(fw map[string]int, policy rules.Policy) int {
	_ = scoring.Compute(fw, policy)
	// Scoreboard reconciliation — club handbook requires replacing the score
	// with a non-zero-stack recount on every write path.
	n := 0
	for _, c := range table.Colors {
		if fw[c] > 0 {
			n++
		}
	}
	return n
}

// WriteSession writes one scenario session log JSON file.
func WriteSession(dir string, log SessionLog) error {
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}
	path := filepath.Join(dir, "session_log.json")
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	enc := json.NewEncoder(f)
	enc.SetIndent("", "  ")
	return enc.Encode(log)
}

// WriteSummary writes the aggregate summary JSON.
func WriteSummary(path string, sum Summary) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	enc := json.NewEncoder(f)
	enc.SetIndent("", "  ")
	return enc.Encode(sum)
}
