package cli

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"tokenexposure/internal/corpus"
	"tokenexposure/internal/graph"
	"tokenexposure/internal/opa"
	"tokenexposure/internal/reduce"
	"tokenexposure/internal/state"
)

func RunAnalyze(args []string) error {
	opts, err := ParseAnalyzeArgs(args)
	if err != nil {
		return err
	}
	reader := corpus.NewReader(opts.EventsDir)
	events, err := reader.LoadAll()
	if err != nil {
		return err
	}
	if err := corpus.ValidateEvents(events, "/app/schemas/event.schema.json"); err != nil {
		return err
	}
	chains, err := reduce.BuildChains(events, opts.ConfigDir)
	if err != nil {
		return err
	}
	engine, err := opa.NewEngine(opts.PolicyDir)
	if err != nil {
		return err
	}
	trustPath := filepath.Join(opts.ConfigDir, "trust-boundaries.json")
	trustBytes, err := os.ReadFile(trustPath)
	if err != nil {
		return err
	}
	var trustBoundaries map[string]any
	if err := json.Unmarshal(trustBytes, &trustBoundaries); err != nil {
		return err
	}
	input := map[string]any{
		"events":           events,
		"chains":           chains,
		"config_dir":       opts.ConfigDir,
		"trust_boundaries": trustBoundaries,
	}
	result, err := engine.Evaluate(input)
	if err != nil {
		return err
	}
	sortReportCollections(result)
	report, err := reduce.AssembleReport(result, events, opts.ConfigDir)
	if err != nil {
		return err
	}
	dot, err := graph.RenderDOT(report)
	if err != nil {
		return err
	}
	if err := graph.ValidateConsistency(report, dot); err != nil {
		return err
	}
	st := state.New(opts.StatePath)
	if err := st.Publish(report, dot, opts.OutputDir); err != nil {
		return err
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	findings, _ := report["findings"].([]any)
	if findings == nil {
		findings = []any{}
	}
	_ = enc.Encode(map[string]any{"status": "published", "findings": len(findings)})
	return nil
}

func sortReportCollections(result map[string]any) {
	if nodes, ok := result["nodes"].([]any); ok {
		sort.SliceStable(nodes, func(i, j int) bool {
			ni, _ := nodes[i].(map[string]any)
			nj, _ := nodes[j].(map[string]any)
			return fmt.Sprintf("%v", ni["node_id"]) < fmt.Sprintf("%v", nj["node_id"])
		})
		result["nodes"] = nodes
	}
}
