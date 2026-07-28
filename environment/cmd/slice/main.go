package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"bsplan/pkg/cache"
	"bsplan/pkg/fingerprint"
	"bsplan/pkg/load"
	"bsplan/pkg/plan"
	"bsplan/pkg/report"
)

const commandEcho = "go run /app/environment/cmd/slice --all-scenarios --write /app/output/buildslice_report.json"

func main() {
	outputPath := flag.String("write", "/app/output/buildslice_report.json", "report output path")
	allScenarios := flag.Bool("all-scenarios", false, "run every scenario manifest")
	flag.Parse()
	if !*allScenarios {
		fmt.Fprintln(os.Stderr, "--all-scenarios is required")
		os.Exit(2)
	}
	if err := run(*outputPath); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run(outputPath string) error {
	graph, graphCanonical, err := load.LoadGraph("/app/environment/vendor_tree/graph.json")
	if err != nil {
		return err
	}
	scenarioFiles, err := load.LoadScenarios("/app/environment/scenarios")
	if err != nil {
		return err
	}
	outputDir := filepath.Dir(outputPath)
	cachePath := filepath.Join(outputDir, "buildslice_cache.json")
	runPath := filepath.Join(outputDir, "buildslice_run.json")
	oldEntries, cacheRebuilt := cache.Read(cachePath)
	currentEntries := map[string]cache.Entry{}
	rows := make([]plan.ScenarioPlan, 0, len(scenarioFiles))
	reused := []string{}
	recomputed := []string{}
	currentIDs := map[string]bool{}
	for _, source := range scenarioFiles {
		scenario := source.Scenario
		currentIDs[scenario.ScenarioID] = true
		inputDigest := fingerprint.InputDigest(graphCanonical, source.Canonical)
		if entry, ok := oldEntries[scenario.ScenarioID]; ok && entry.InputDigest == inputDigest {
			rows = append(rows, entry.Plan)
			currentEntries[scenario.ScenarioID] = entry
			reused = append(reused, scenario.ScenarioID)
			continue
		}
		value, err := plan.BuildScenario(graph, scenario, inputDigest)
		if err != nil {
			return err
		}
		entry := cache.Entry{ScenarioID: scenario.ScenarioID, InputDigest: inputDigest, Plan: value}
		rows = append(rows, value)
		currentEntries[scenario.ScenarioID] = entry
		recomputed = append(recomputed, scenario.ScenarioID)
	}
	removed := []string{}
	for id := range oldEntries {
		if !currentIDs[id] {
			removed = append(removed, id)
		}
	}
	sort.Strings(reused)
	sort.Strings(recomputed)
	sort.Strings(removed)
	reportFile := report.Build(commandEcho, rows)
	cacheFile := cache.Build(currentEntries)
	runFile := cache.Run{
		SchemaVersion: 1,
		Reused:        reused,
		Recomputed:    recomputed,
		Removed:       removed,
		CacheRebuilt:  cacheRebuilt,
		CacheDigest:   cache.Digest(cacheFile),
		ReportDigest:  reportFile.Summary.ReportDigest,
	}
	return report.WriteAtomic([]report.Artifact{
		{Path: outputPath, Value: reportFile},
		{Path: cachePath, Value: cacheFile},
		{Path: runPath, Value: runFile},
	})
}
