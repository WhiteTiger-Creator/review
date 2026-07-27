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
	var policyPath string
	var outputPath string

	flag.StringVar(&policyPath, "policy", "/app/spec/mesh_policy.json", "Path to mesh policy file")
	flag.StringVar(&outputPath, "output", "/app/output/posture.json", "Path to posture output file")

	dataRootPtr := flag.String("data-root", "/app/data", "Path to data root directory")
	dataPtr := flag.String("data", "", "Path to data root directory (alias)")

	flag.Parse()

	args := flag.Args()
	if len(args) > 0 {
		if args[0] != "reconcile" {
			die("unknown subcommand '" + args[0] + "'. Only 'reconcile' is supported.")
		}
	}

	dataRoot := *dataRootPtr
	if *dataPtr != "" {
		dataRoot = *dataPtr
	}

	report, err := mesh.RunReconcile(dataRoot, policyPath)
	if err != nil {
		die(err.Error())
	}

	if err := mesh.WritePosture(report, outputPath); err != nil {
		die(err.Error())
	}
}
