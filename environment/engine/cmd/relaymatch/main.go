package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"fog-chess-relay/internal/integrity"
	"fog-chess-relay/internal/match"
)

func main() {
	root := env("FOG_CHESS_ROOT", "/opt/fog-chess-relay")
	output := env("FOG_CHESS_OUTPUT", "/app/output")
	var (
		cmdVerify   = flag.Bool("verify-assets", false, "verify integrity manifest")
		cmdMatch    = flag.String("match", "", "position id or path")
		botPath     = flag.String("bot", "/app/work/playbook", "playbook directory containing strategy.json")
		compile     = flag.Bool("compile", false, "legacy: compile a Go bot directory (unused for sealed player)")
		checkBook   = flag.Bool("check-playbook", false, "validate strategy.json exists and parses")
		injectFail  = flag.String("inject-fail", "", "validation|rename|pointer")
		buildManifest = flag.Bool("build-manifest", false, "rebuild integrity manifest")
		listPublic  = flag.Bool("list-public", false, "list public positions")
	)
	flag.Parse()

	c := &match.Controller{Root: root, OutputRoot: output, InjectFail: *injectFail}

	if *buildManifest {
		paths, err := integrity.CollectRelPaths(root, "positions/", "opponents/", "contracts/", "notation/")
		if err != nil {
			fatal(err)
		}
		man, err := integrity.BuildManifest(root, paths)
		if err != nil {
			fatal(err)
		}
		if err := os.MkdirAll(filepath.Join(root, "integrity"), 0o755); err != nil {
			fatal(err)
		}
		if err := integrity.WriteManifest(filepath.Join(root, "integrity", "manifest.json"), man); err != nil {
			fatal(err)
		}
		fmt.Println("manifest written")
		return
	}

	if *cmdVerify {
		if err := c.VerifyAssets(); err != nil {
			fatal(err)
		}
		fmt.Println("ok")
		return
	}

	if *listPublic {
		entries, _ := os.ReadDir(filepath.Join(root, "positions", "public"))
		for _, e := range entries {
			fmt.Println(e.Name())
		}
		return
	}

	if *checkBook {
		p := filepath.Join(*botPath, "strategy.json")
		b, err := os.ReadFile(p)
		if err != nil {
			fatal(err)
		}
		var obj map[string]any
		if err := json.Unmarshal(b, &obj); err != nil {
			fatal(err)
		}
		if _, ok := obj["fallback"]; !ok {
			fatal(fmt.Errorf("playbook missing fallback"))
		}
		if rules, ok := obj["rules"]; ok {
			if arr, ok := rules.([]any); ok && len(arr) > 24 {
				fatal(fmt.Errorf("playbook has more than 24 rules"))
			}
		}
		fmt.Println("ok")
		return
	}

	if *cmdMatch != "" {
		path := *cmdMatch
		if !filepath.IsAbs(path) && !fileExists(path) {
			cand := filepath.Join(root, "positions", "public", path+".json")
			if fileExists(cand) {
				path = cand
			} else {
				cand = filepath.Join(root, "positions", path+".json")
				if fileExists(cand) {
					path = cand
				}
			}
		}
		if err := os.MkdirAll(filepath.Join(output, "generations"), 0o755); err != nil {
			fatal(err)
		}
		if err := c.RunMatch(match.PathOrSpec{Path: path}, *botPath, *compile); err != nil {
			fatal(err)
		}
		fmt.Println("match_complete")
		return
	}

	fmt.Fprintf(os.Stderr, "usage: relaymatch -match <id|path> [-bot path]\n")
	os.Exit(2)
}

func env(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

func fileExists(p string) bool {
	_, err := os.Stat(p)
	return err == nil
}

func fatal(err error) {
	enc := json.NewEncoder(os.Stderr)
	_ = enc.Encode(map[string]string{"error": err.Error()})
	os.Exit(1)
}
