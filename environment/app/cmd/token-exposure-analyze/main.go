package main

import (
	"os"

	"tokenexposure/internal/cli"
)

func main() {
	if err := cli.RunAnalyze(os.Args[1:]); err != nil {
		os.Stderr.WriteString(err.Error() + "\n")
		os.Exit(1)
	}
}
