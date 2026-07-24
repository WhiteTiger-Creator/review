package main

import (
	"encoding/json"
	"os"
	"path/filepath"

	"depctrl/w3j"
	"depctrl/x8c"
)

func runGate() error {
	if err := ensureOut(); err != nil {
		return err
	}
	graph, toggles, err := loadSeedGraph()
	if err != nil {
		return err
	}
	staging := map[string]any{
		"partial":  true,
		"edge_n":   len(graph.Edges),
		"toggle_n": len(toggles),
	}
	if err := writeJSON(stagingPath, staging); err != nil {
		return err
	}
	return writeJSON(filepath.Join(runTraceDir, "gate.json"), staging)
}

func loadSeedGraph() (x8c.GraphView, map[string]bool, error) {
	b, err := os.ReadFile(filepath.Join(dataRoot, "seed_lock.json"))
	if err != nil {
		return x8c.GraphView{}, nil, err
	}
	var seed struct {
		Edges []x8c.Edge `json:"edges"`
	}
	if err := json.Unmarshal(b, &seed); err != nil {
		return x8c.GraphView{}, nil, err
	}
	toggleBytes, err := os.ReadFile(filepath.Join(dataRoot, "act_map.json"))
	if err != nil {
		return x8c.GraphView{}, nil, err
	}
	toggles := map[string]bool{}
	if err := json.Unmarshal(toggleBytes, &toggles); err != nil {
		return x8c.GraphView{}, nil, err
	}
	lines, err := loadRawLines()
	if err != nil {
		// gate may run before collect in manual mode; tolerate empty
		lines = nil
	}
	actSeen := map[string]bool{}
	for _, ln := range lines {
		raw, err := w3j.ParseLoose(ln.Bytes)
		if err != nil {
			continue
		}
		if v, ok := raw["act_tok"].(string); ok && v != "" {
			actSeen[v] = true
		}
	}
	for i := range seed.Edges {
		if seed.Edges[i].Optional {
			seed.Edges[i].ActPresent = actSeen[seed.Edges[i].ActKey]
		}
	}
	return x8c.GraphView{Edges: seed.Edges}, toggles, nil
}
