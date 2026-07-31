package cli

import (
	"fmt"
	"os"
)

func invalid() int {
	fmt.Fprintln(os.Stderr, "drainwave: invalid input")
	return 2
}

func ioFailure() int {
	fmt.Fprintln(os.Stderr, "drainwave: io error")
	return 1
}
