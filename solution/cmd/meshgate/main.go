package main

import (
	"flag"
	"fmt"
	"os"
	"meshgate/internal/mesh"
)

func die(msg string) {
	fmt.Fprintf(os.Stderr, "Error: %s\n", msg)
	os.Exit(1)
}

func main() {
	args := os.Args[1:]
	if len(args) > 0 && args[0] == "reconcile" {
		args = args[1:]
	} else if len(args) > 0 && args[0] != "" && args[0][0] != '-' {
		die("unknown subcommand '" + args[0] + "'. Only 'reconcile' is supported.")
	}

	fs := flag.NewFlagSet("meshgate", flag.ExitOnError)
	policyPath := fs.String("policy", "/app/spec/mesh_policy.json", "Path to mesh policy file")
	outputPath := fs.String("output", "/app/output/posture.json", "Path to posture output file")
	dataRootPtr := fs.String("data-root", "/app/data", "Path to data root directory")
	dataPtr := fs.String("data", "", "Path to data root directory (alias)")

	if err := fs.Parse(args); err != nil {
		die(err.Error())
	}
	if fs.NArg() > 0 {
		die("unexpected extra arguments")
	}

	dataRoot := *dataRootPtr
	if *dataPtr != "" {
		dataRoot = *dataPtr
	}

	report, err := mesh.RunReconcile(dataRoot, *policyPath)
	if err != nil {
		die(err.Error())
	}

	if err := mesh.WritePosture(report, *outputPath); err != nil {
		die(err.Error())
	}
}
