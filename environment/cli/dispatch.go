package cli

import (
	"fmt"
	"os"
)

func Run(args []string) int {
	if len(args) < 1 {
		fmt.Fprintln(os.Stderr, "usage: etaengine <status|stage|finalize|commit|rollback|evaluate|replay> ...")
		return 2
	}
	cmd := args[0]
	rest := args[1:]
	switch cmd {
	case "status":
		return cmdStatus(rest)
	case "stage":
		return cmdStage(rest)
	case "finalize":
		return cmdFinalize(rest)
	case "commit":
		return cmdCommit(rest)
	case "rollback":
		return cmdRollback(rest)
	case "evaluate":
		return cmdEvaluate(rest)
	case "replay":
		return cmdReplay(rest)
	default:
		fmt.Fprintln(os.Stderr, "unknown command")
		return 2
	}
}
