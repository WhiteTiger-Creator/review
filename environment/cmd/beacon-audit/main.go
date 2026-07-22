package main

import (
	"fmt"
	"os"

	"beaconaudit/internal/cli"
)

func main() {
	if err := cli.Run(os.Args[1:], os.Stdout); err != nil {
		fmt.Fprintln(os.Stderr, "beacon-audit:", err)
		os.Exit(2)
	}
}
