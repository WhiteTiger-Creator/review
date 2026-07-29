package main

import (
	"fmt"
	"os"

	"stormlab/clk"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: epochctl invalidate|restore")
		os.Exit(2)
	}
	var err error
	switch os.Args[1] {
	case "invalidate":
		err = clk.InvalidateK()
	case "restore":
		err = clk.RestoreP()
	default:
		fmt.Fprintln(os.Stderr, "usage: epochctl invalidate|restore")
		os.Exit(2)
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
