package main

import (
	"fmt"
	"os"
)

// reclaim is the snapshot reclaim supervisor described in /app/PROTOCOL.md.
// This is an unimplemented skeleton: build the `reclaim plan` command so that it
// reads the pool records, works out what each pool keeps and releases under the
// manual's rules, and writes the report. Replace this file (and add whatever
// packages you need) with a working implementation.
func main() {
	fmt.Fprintln(os.Stderr, "reclaim: not implemented")
	os.Exit(1)
}
