package load

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

type Import struct {
	Path     string `json:"path"`
	Optional bool   `json:"optional"`
	Priority int    `json:"priority"`
}

type Package struct {
	ImportPath string     `json:"import_path"`
	TagSets    [][]string `json:"tag_sets"`
	Imports    []Import   `json:"imports"`
}

type Replace struct {
	Old string `json:"old"`
	New string `json:"new"`
}

type Graph struct {
	SchemaVersion int       `json:"schema_version"`
	Module        string    `json:"module"`
	Retired       []string  `json:"retired"`
	Replaces      []Replace `json:"replaces"`
	Packages      []Package `json:"packages"`
}

type Scenario struct {
	ScenarioID string   `json:"scenario_id"`
	Tags       []string `json:"tags"`
	Roots      []string `json:"roots"`
	Ceiling    int      `json:"ceiling"`
}

type ScenarioFile struct {
	Path      string
	Scenario  Scenario
	Canonical []byte
}

func CanonicalJSON(raw []byte) ([]byte, error) {
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	var value any
	if err := decoder.Decode(&value); err != nil {
		return nil, err
	}
	if decoder.More() {
		return nil, fmt.Errorf("multiple JSON values")
	}
	return json.Marshal(value)
}

func LoadGraph(path string) (*Graph, []byte, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, nil, err
	}
	canonical, err := CanonicalJSON(raw)
	if err != nil {
		return nil, nil, fmt.Errorf("graph JSON: %w", err)
	}
	var graph Graph
	if err := json.Unmarshal(raw, &graph); err != nil {
		return nil, nil, fmt.Errorf("graph decode: %w", err)
	}
	if graph.SchemaVersion != 1 {
		return nil, nil, fmt.Errorf("graph schema_version must be 1")
	}
	if strings.TrimSpace(graph.Module) == "" {
		return nil, nil, fmt.Errorf("graph module is empty")
	}
	seen := map[string]bool{}
	for _, pkg := range graph.Packages {
		if strings.TrimSpace(pkg.ImportPath) == "" {
			return nil, nil, fmt.Errorf("package import_path is empty")
		}
		if seen[pkg.ImportPath] {
			return nil, nil, fmt.Errorf("duplicate package %q", pkg.ImportPath)
		}
		seen[pkg.ImportPath] = true
	}
	return &graph, canonical, nil
}

func LoadScenarios(dir string) ([]ScenarioFile, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	files := make([]ScenarioFile, 0, len(entries))
	ids := map[string]bool{}
	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".json") {
			continue
		}
		path := filepath.Join(dir, entry.Name())
		raw, err := os.ReadFile(path)
		if err != nil {
			return nil, err
		}
		canonical, err := CanonicalJSON(raw)
		if err != nil {
			return nil, fmt.Errorf("scenario %s JSON: %w", entry.Name(), err)
		}
		var scenario Scenario
		if err := json.Unmarshal(raw, &scenario); err != nil {
			return nil, fmt.Errorf("scenario %s decode: %w", entry.Name(), err)
		}
		if strings.TrimSpace(scenario.ScenarioID) == "" {
			return nil, fmt.Errorf("scenario %s has empty scenario_id", entry.Name())
		}
		if ids[scenario.ScenarioID] {
			return nil, fmt.Errorf("duplicate scenario_id %q", scenario.ScenarioID)
		}
		ids[scenario.ScenarioID] = true
		files = append(files, ScenarioFile{Path: path, Scenario: scenario, Canonical: canonical})
	}
	sort.Slice(files, func(i, j int) bool {
		return files[i].Scenario.ScenarioID < files[j].Scenario.ScenarioID
	})
	return files, nil
}
