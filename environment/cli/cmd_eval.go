package cli

import (
	"fmt"
	"os"
	"strconv"

	"github.com/local/etaengine/runtrail"
	"github.com/local/etaengine/shipkv"
	"github.com/local/etaengine/types"
)

func cmdEvaluate(args []string) int {
	fm := flagMap(args)
	root := orDefault(fm["root"], "/app/environment")
	fixture := fm["fixture"]
	family := orDefault(fm["family"], "base")
	out := fm["out"]
	seed, _ := strconv.ParseUint(orDefault(fm["seed"], "0"), 10, 64)
	key := orDefault(fm["key"], fmt.Sprintf("%s:%s:%d", fixture, family, seed))
	if fixture == "" || out == "" {
		fmt.Fprintln(os.Stderr, "fixture and out required")
		return 2
	}
	settings, gen, epoch, err := shipkv.ResolveEvalKnobs(root)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	reg, err := shipkv.LoadRegistry(root)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	doc, err := runEval(root, fixture, family, seed, settings, gen, reg.ModelID)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	if err := writeDoc(out, doc); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	entry := types.LedgerEntry{
		Key:        key,
		Generation: gen,
		Fixture:    fixture,
		Family:     family,
		Seed:       seed,
		OutPath:    out,
		EpochToken: epoch,
	}
	if err := runtrail.Append(root, entry); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	return 0
}
