package main

import (
	"fmt"
	"os"
	"path/filepath"

	"skiff/internal/report"
	"skiff/internal/scene"
	"skiff/internal/world"
)

func main() {
	root := "."
	if v := os.Getenv("SKIFF_ROOT"); v != "" {
		root = v
	}
	if len(os.Args) > 1 {
		root = os.Args[1]
	}
	root, _ = filepath.Abs(root)
	bundle, err := scene.LoadBundle(root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "bundle: %v\n", err)
		os.Exit(1)
	}
	rows := make([]report.CaseRow, 0, len(bundle.Cases))
	for _, id := range bundle.Cases {
		c, err := scene.LoadCase(root, id)
		if err != nil {
			fmt.Fprintf(os.Stderr, "case %s: %v\n", id, err)
			os.Exit(1)
		}
		res := world.Run(c)
		rows = append(rows, report.RowFrom(id, res))
	}
	if err := report.Write(root, bundle, rows); err != nil {
		fmt.Fprintf(os.Stderr, "write: %v\n", err)
		os.Exit(1)
	}
}
