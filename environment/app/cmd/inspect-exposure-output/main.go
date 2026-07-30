package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"tokenexposure/internal/graph"
)

func main() {
	reportPath := flag.String("report", "/output/token_exposure_report.json", "report json")
	dotPath := flag.String("dot", "/output/token_exposure_graph.dot", "graph dot")
	flag.Parse()
	reportBytes, err := os.ReadFile(*reportPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	dotBytes, err := os.ReadFile(*dotPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	var report map[string]any
	if err := json.Unmarshal(reportBytes, &report); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := graph.ValidateConsistency(report, string(dotBytes)); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Println("exposure output consistent")
}
