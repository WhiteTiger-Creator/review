package cli

import (
	"fmt"
	"os"
	"strconv"

	"github.com/local/etaengine/krel"
	"github.com/local/etaengine/types"
)

func cmdStage(args []string) int {
	fm := flagMap(args)
	root := orDefault(fm["root"], "/app/environment")
	mode := orDefault(fm["scale-mode"], "peak")
	gw, _ := strconv.ParseFloat(orDefault(fm["graph-weight"], "0.005"), 32)
	lw, _ := strconv.ParseFloat(orDefault(fm["lane-weight"], "0.995"), 32)
	s := types.InferSettings{ScaleMode: mode, GraphWeight: float32(gw), LaneWeight: float32(lw)}
	if err := krel.Stage(root, s); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	return 0
}

func cmdFinalize(args []string) int {
	fm := flagMap(args)
	root := orDefault(fm["root"], "/app/environment")
	if err := krel.Finalize(root); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	return 0
}

func cmdCommit(args []string) int {
	fm := flagMap(args)
	root := orDefault(fm["root"], "/app/environment")
	if err := krel.ActivateCutover(root); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	return 0
}

func cmdRollback(args []string) int {
	fm := flagMap(args)
	root := orDefault(fm["root"], "/app/environment")
	if err := krel.Rollback(root); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	return 0
}
