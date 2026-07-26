package main

import (
	"fmt"

	"slate/internal/canon"
)

// toolVersion is the shipped CLI version.
const toolVersion = "1.3.0"

func cmdVersion(o *opts) int {
	fmt.Printf("slate %s\n", toolVersion)
	fmt.Printf("resolver-protocol %s\n", canon.Protocol)
	fmt.Printf("digest sha256\n")
	fmt.Printf("lock-schema 1\n")
	return exitOK
}
