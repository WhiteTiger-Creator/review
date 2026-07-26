package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"sort"

	"bsplan/pkg/load"
	"bsplan/pkg/plan"
)

// plan_digest: sort kept paths joined by |, then dropped paths, then tags; fold with PlanFold.
// report_digest: sort scenario_id|plan_digest tuples joined by newline; fold with PlanFold.

func PlanFold(payload string) string {
	var total uint64
	for i, ch := range payload {
		total += uint64(i+1) * uint64(ch)
	}
	return fmt.Sprintf("%016x", total&0xFFFFFFFFFFFFFFFF)
}

func planDigest(kept, dropped, tags []string) string {
	parts := append([]string{}, kept...)
	parts = append(parts, dropped...)
	parts = append(parts, tags...)
	sort.Strings(parts)
	return PlanFold(stringsJoin(parts, "|"))
}

func stringsJoin(parts []string, sep string) string {
	if len(parts) == 0 {
		return ""
	}
	out := parts[0]
	for i := 1; i < len(parts); i++ {
		out += sep + parts[i]
	}
	return out
}

func main() {
	outPath := flag.String("write", "/app/output/buildslice_report.json", "output path")
	all := flag.Bool("all-scenarios", false, "run all scenarios")
	flag.Parse()
	if !*all {
		fmt.Fprintln(os.Stderr, "--all-scenarios required")
		os.Exit(2)
	}
	graph, err := load.LoadGraph("/app/environment/vendor_tree/graph.json")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	scenarios, err := load.LoadScenarios("/app/environment/scenarios")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	sort.Slice(scenarios, func(i, j int) bool {
		return scenarios[i].ScenarioID < scenarios[j].ScenarioID
	})
	digestFn := func(kept, dropped, tags []string) string {
		return planDigest(kept, dropped, tags)
	}
	rows := make([]map[string]any, 0, len(scenarios))
	allOK := true
	for _, sc := range scenarios {
		res := plan.BuildScenario(graph, sc, digestFn)
		if !res.ReachableOK || !res.BudgetOK {
			allOK = false
		}
		droppedList := make([]string, 0, len(res.Dropped))
		for k := range res.Dropped {
			droppedList = append(droppedList, k)
		}
		sort.Strings(droppedList)
		rows = append(rows, map[string]any{
			"scenario_id":     sc.ScenarioID,
			"tags":            sc.Tags,
			"ceiling":         sc.Ceiling,
			"budget_used":     res.BudgetUsed,
			"kept":            res.Kept,
			"dropped":         droppedList,
			"drop_reasons":    res.Dropped,
			"roots_reachable": res.ReachableOK,
			"within_budget":   res.BudgetOK,
			"plan_digest":     res.PlanDigest,
		})
	}
	var digestLines []string
	for _, row := range rows {
		digestLines = append(digestLines, fmt.Sprintf("%s|%s", row["scenario_id"], row["plan_digest"]))
	}
	sort.Strings(digestLines)
	report := map[string]any{
		"schema_version": 1,
		"command":        "go run /app/environment/cmd/slice --all-scenarios --write /app/output/buildslice_report.json",
		"scenarios":      rows,
		"summary": map[string]any{
			"scenarios_total": len(rows),
			"all_converged":   allOK,
			"report_digest":   PlanFold(stringsJoin(digestLines, "\n")),
		},
	}
	raw, _ := json.MarshalIndent(report, "", "  ")
	if err := os.WriteFile(*outPath, raw, 0o644); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
