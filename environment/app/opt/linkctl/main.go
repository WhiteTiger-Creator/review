package main

import (
	"os"
	"path/filepath"
)

func settleRoot(root string) string {
	return buildReport(newSettlement(loadHost(root)).run())
}

func clearDir(dir string) error {
	if err := os.MkdirAll(dir, 0o777); err != nil {
		return err
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		return err
	}
	for _, entry := range entries {
		if err := os.RemoveAll(filepath.Join(dir, entry.Name())); err != nil {
			return err
		}
	}
	return nil
}

func file(target string, text string) error {
	if err := clearDir(filepath.Dir(target)); err != nil {
		return err
	}
	return os.WriteFile(target, []byte(text), 0o666)
}

func main() {
	root := os.Getenv("LINK_ROOT")
	if root == "" {
		root = "/app/host"
	}
	target := os.Getenv("LINK_STATE_REPORT")
	if target == "" {
		target = "/app/var/lib/linkctl/link-state-report.txt"
	}
	selfcheck := false
	for _, arg := range os.Args[1:] {
		if arg == "--selfcheck" {
			selfcheck = true
		}
	}
	text := settleRoot(root)
	if selfcheck {
		again := settleRoot(root)
		if again != text {
			os.Exit(1)
		}
		if err := file(target, again); err != nil {
			os.Exit(1)
		}
		return
	}
	if err := file(target, text); err != nil {
		os.Exit(1)
	}
}
