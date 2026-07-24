package main

import (
	"fmt"
	"os"

	"meshgridfix/internal/mesh"
)

func main() {
	root := "/app/meshgrid"
	outPath := "/app/build/gradle_stabilization_report.json"
	report, err := mesh.Analyze(root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "analyze: %v\n", err)
		os.Exit(1)
	}
	if err := os.MkdirAll("/app/build", 0o755); err != nil {
		fmt.Fprintf(os.Stderr, "mkdir: %v\n", err)
		os.Exit(1)
	}
	if err := mesh.WriteReport(outPath, report); err != nil {
		fmt.Fprintf(os.Stderr, "write: %v\n", err)
		os.Exit(1)
	}
}
