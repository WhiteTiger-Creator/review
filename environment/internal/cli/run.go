package cli

import (
	"encoding/json"
	"os"
	"path/filepath"

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
	if err := corpus.ValidateEvents(events, filepath.Join(opts.ConfigDir, "..", "schemas", "event.schema.json")); err != nil {
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
	input := map[string]any{
		"events": events,
		"chains": chains,
		"config_dir": opts.ConfigDir,
	}
	result, err := engine.Evaluate(input)
	if err != nil {
		return err
	}
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
	_ = enc.Encode(map[string]any{"status": "published", "findings": len(report["findings"].([]any))})
	return nil
}
