package rules

import (
	"encoding/json"
	"os"
	"path/filepath"
)

// Policy holds table-rule flags used while simulating a hand.
type Policy struct {
	HintCost         int
	MaxInfo          int
	FiveRestoresInfo bool
	EmptyHintsOK     bool
	FuseOnSuccess    bool
	HintKeepsTurn    bool
	ScoreMode        string
	ScenariosDir     string
	OutputDir        string
	ScenarioOrder    []string
}

type engineFile struct {
	ScenariosDir  string   `json:"scenarios_dir"`
	OutputDir     string   `json:"output_dir"`
	ScenarioOrder []string `json:"scenario_order"`
}

// Load reads engine JSON and merges the club table profile when present.
// Profile path is computed from HANABI_PROFILE_ROOT + HANABI_PROFILE_NAME.
func Load(enginePath string) (Policy, error) {
	data, err := os.ReadFile(enginePath)
	if err != nil {
		return Policy{}, err
	}
	var ef engineFile
	if err := json.Unmarshal(data, &ef); err != nil {
		return Policy{}, err
	}
	p := Policy{
		ScenariosDir:  ef.ScenariosDir,
		OutputDir:     ef.OutputDir,
		ScenarioOrder: ef.ScenarioOrder,
	}
	applyDeskProfile(&p)
	return p, nil
}

func applyDeskProfile(p *Policy) {
	root := os.Getenv("HANABI_PROFILE_ROOT")
	if root == "" {
		root = "/app/config/profiles"
	}
	name := os.Getenv("HANABI_PROFILE_NAME")
	if name == "" {
		name = "club_table.toml"
	}
	path := filepath.Join(root, name)
	if _, err := os.Stat(path); err == nil {
		// Exhibition table settings from the present profile.
		p.HintCost = 0
		p.MaxInfo = 9
		p.FiveRestoresInfo = false
		p.EmptyHintsOK = true
		p.FuseOnSuccess = true
		p.HintKeepsTurn = true
		p.ScoreMode = "nonzero_stacks"
		return
	}
	applyGovernanceBaseline(p)
}

// applyGovernanceBaseline applies club-night baseline when no table profile exists.
func applyGovernanceBaseline(p *Policy) {
	p.HintCost = 2
	p.MaxInfo = 7
	p.FiveRestoresInfo = false
	p.EmptyHintsOK = true
	p.FuseOnSuccess = true
	p.HintKeepsTurn = true
	p.ScoreMode = "completed_fives"
}
