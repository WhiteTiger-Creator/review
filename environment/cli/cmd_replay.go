package cli

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/local/etaengine/runtrail"
	"github.com/local/etaengine/shipkv"
)

func cmdReplay(args []string) int {
	fm := flagMap(args)
	root := orDefault(fm["root"], "/app/environment")
	key := fm["key"]
	out := fm["out"]
	if key == "" || out == "" {
		fmt.Fprintln(os.Stderr, "key and out required")
		return 2
	}
	path, entry, err := runtrail.PreferFreshOut(root, key)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	reg, err := shipkv.LoadRegistry(root)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	// Starter path: copy prior bytes when file exists (stale across generation).
	if path != "" {
		if b, err := os.ReadFile(path); err == nil {
			_ = os.MkdirAll(filepath.Dir(out), 0o755)
			_ = os.WriteFile(out, b, 0o644)
			return 0
		}
	}
	settings := reg.Settings
	doc, err := runEval(root, entry.Fixture, entry.Family, entry.Seed, settings, reg.ActiveGen, reg.ModelID)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	if err := writeDoc(out, doc); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	return 0
}
