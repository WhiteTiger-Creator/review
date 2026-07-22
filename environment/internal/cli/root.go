package cli

import (
	"fmt"
	"io"
)

const usage = `beacon-audit retains and validates NIST Randomness Beacon 2.0 evidence.

Usage:
  beacon-audit acquire --case FILE --directory DIR
  beacon-audit verify --case FILE --directory DIR --receipt FILE
  beacon-audit help
`

func Run(arguments []string, stdout io.Writer) error {
	if len(arguments) == 0 {
		_, _ = fmt.Fprint(stdout, usage)
		return fmt.Errorf("command is required")
	}
	switch arguments[0] {
	case "help", "--help", "-h":
		_, err := fmt.Fprint(stdout, usage)
		return err
	case "acquire":
		return runAcquire(arguments[1:])
	case "verify":
		return runVerify(arguments[1:])
	default:
		return fmt.Errorf("unknown command %q", arguments[0])
	}
}
