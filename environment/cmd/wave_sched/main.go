package main

import (
	"flag"
	"os"

	"stormlab/driver"
)

func main() {
	gridFull := flag.Bool("grid-full", false, "")
	out := flag.String("out", "/app/output/storm_trace.json", "")
	flag.Parse()
	if !*gridFull {
		os.Exit(2)
	}
	os.Exit(driver.RunGridFull(*out))
}
