package load

import (
	"encoding/json"
	"os"
	"strings"
)

type Package struct {
	ImportPath string     `json:"import_path"`
	TagSets    [][]string `json:"tag_sets"`
	Imports    []string   `json:"imports"`
	Optional   bool       `json:"optional"`
}

type Graph struct {
	Module   string    `json:"module"`
	Retired  []string  `json:"retired"`
	Packages []Package `json:"packages"`
	Replaces []Replace `json:"replaces"`
}

type Replace struct {
	Old   string `json:"old"`
	New   string `json:"new"`
	Local string `json:"local"`
}

type Scenario struct {
	ScenarioID string   `json:"scenario_id"`
	Tags       []string `json:"tags"`
	Roots      []string `json:"roots"`
	Ceiling    int      `json:"ceiling"`
}

func LoadGraph(path string) (*Graph, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var g Graph
	if err := json.Unmarshal(raw, &g); err != nil {
		return nil, err
	}
	return &g, nil
}

func LoadScenarios(dir string) ([]Scenario, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	out := make([]Scenario, 0, len(entries))
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".json") {
			continue
		}
		raw, err := os.ReadFile(dir + "/" + e.Name())
		if err != nil {
			return nil, err
		}
		var sc Scenario
		if err := json.Unmarshal(raw, &sc); err != nil {
			return nil, err
		}
		out = append(out, sc)
	}
	return out, nil
}

func ReplaceTable(g *Graph) map[string]string {
	table := map[string]string{}
	for _, r := range g.Replaces {
		table[r.Old] = r.New
	}
	return table
}

func OptionalMap(g *Graph) map[string]bool {
	m := map[string]bool{}
	for _, p := range g.Packages {
		if p.Optional {
			m[p.ImportPath] = true
		}
	}
	return m
}

func EdgeMap(g *Graph) map[string][]string {
	m := map[string][]string{}
	for _, p := range g.Packages {
		m[p.ImportPath] = append([]string{}, p.Imports...)
	}
	return m
}

func PackageByPath(g *Graph) map[string]Package {
	m := map[string]Package{}
	for _, p := range g.Packages {
		m[p.ImportPath] = p
	}
	return m
}

func RetiredSet(g *Graph) map[string]bool {
	m := map[string]bool{}
	for _, r := range g.Retired {
		m[r] = true
	}
	return m
}
