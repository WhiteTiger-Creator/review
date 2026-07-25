package main

import (
	"flag"
	"fmt"
	"os"

	"wgmeshd/internal/opsprofile"
	"wgmeshd/internal/peermesh"
	"wgmeshd/internal/meshgate"
	"wgmeshd/internal/meshplan"
	"wgmeshd/internal/dashalign"
)

func main() {
	inventory := flag.String("inventory", "/app/inventory", "inventory root")
	config := flag.String("config", "/app/config", "config directory")
	out := flag.String("out", "/app/output", "output directory")
	flag.Parse()

	cfg := opsprofile.Load(*config)
	corpus, err := peermesh.Load(*inventory)
	if err != nil {
		fmt.Fprintf(os.Stderr, "load inventory: %v\n", err)
		os.Exit(1)
	}
	raw := meshgate.Analyze(corpus, cfg)
	report := meshplan.Score(raw, cfg)
	report = dashalign.Reconcile(report)
	if err := meshplan.Emit(*out, report); err != nil {
		fmt.Fprintf(os.Stderr, "emit: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("wrote %s/mesh_plan.json (%d peers)\n", *out, report.PeersAnalyzed)
}
