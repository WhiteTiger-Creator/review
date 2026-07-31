package main

import (
	"os"

	"racklight/drainwave/internal/cli"
)

func main() {
	os.Exit(cli.Run(os.Args[1:]))
}
