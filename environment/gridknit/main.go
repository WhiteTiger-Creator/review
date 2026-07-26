package main

import (
	"fmt"
	"os"
	"path/filepath"

	"meshgrid.fix/internal/mesh"
)

func main() {
	root := "/app/meshgrid"
	if v := os.Getenv("GRIDKNIT_DATA_ROOT"); v != "" {
		root = v
	}
	outPath := "/app/build/gradle_stabilization_report.json"
	if v := os.Getenv("GRIDKNIT_REPORT_PATH"); v != "" {
		outPath = v
	}
	report, err := mesh.Analyze(root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "analyze: %v\n", err)
		os.Exit(1)
	}
	if err := os.MkdirAll(filepath.Dir(outPath), 0o755); err != nil {
		fmt.Fprintf(os.Stderr, "mkdir: %v\n", err)
		os.Exit(1)
	}
	if err := mesh.WriteReport(outPath, report); err != nil {
		fmt.Fprintf(os.Stderr, "write: %v\n", err)
		os.Exit(1)
	}
}
