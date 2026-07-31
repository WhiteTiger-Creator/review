package board

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
)

// Move is one ring slide in a championship fixture.
type Move struct {
	Side       string `json:"side"`
	From       int    `json:"from"`
	To         int    `json:"to"`
	Path       []int  `json:"path"`
	RemoveRing int    `json:"remove_ring"`
}

// Scenario is one championship match fixture.
type Scenario struct {
	MatchID   string  `json:"match_id"`
	PlayerA   string  `json:"player_a"`
	PlayerB   string  `json:"player_b"`
	StartSide string  `json:"start_side"`
	Markers   []int   `json:"markers"`
	RingsA    []int   `json:"rings_a"`
	RingsB    []int   `json:"rings_b"`
	Lines     [][]int `json:"lines"`
	Moves     []Move  `json:"moves"`
}

// LoadScenarios reads every JSON fixture under dir, sorted by match_id.
func LoadScenarios(dir string) ([]Scenario, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	var paths []string
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		if filepath.Ext(e.Name()) != ".json" {
			continue
		}
		paths = append(paths, filepath.Join(dir, e.Name()))
	}
	sort.Strings(paths)
	out := make([]Scenario, 0, len(paths))
	for _, p := range paths {
		raw, err := os.ReadFile(p)
		if err != nil {
			return nil, err
		}
		var sc Scenario
		if err := json.Unmarshal(raw, &sc); err != nil {
			return nil, err
		}
		if sc.StartSide == "" {
			sc.StartSide = "A"
		}
		for i := range sc.Moves {
			if sc.Moves[i].Path == nil {
				sc.Moves[i].Path = []int{}
			}
		}
		// Omitted remove_ring defaults to 0 in encoding/json; treat missing as -1.
		var probe struct {
			Moves []map[string]any `json:"moves"`
		}
		_ = json.Unmarshal(raw, &probe)
		for j, mv := range probe.Moves {
			if _, ok := mv["remove_ring"]; !ok {
				sc.Moves[j].RemoveRing = -1
			}
		}
		out = append(out, sc)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].MatchID < out[j].MatchID })
	return out, nil
}
