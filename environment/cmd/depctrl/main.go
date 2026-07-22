package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

const (
	envRoot     = "/app/environment"
	dataRoot    = envRoot + "/data"
	outRoot     = "/app/output"
	reportPath  = outRoot + "/constraint_report.json"
	stagingPath = outRoot + "/staging_report.json"
	traceDir    = outRoot + "/traces"
	runTraceDir = outRoot + "/run_traces"
	journalDir  = outRoot + "/journal"
	cacheDir    = outRoot + "/cache"
	walPath     = journalDir + "/lock.wal"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: depctrl <collect|reconcile|emit|status> [--all-mirrors]")
		os.Exit(2)
	}
	cmd := os.Args[1]
	switch cmd {
	case "collect":
		if err := runCollect(); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	case "reconcile":
		all := len(os.Args) > 2 && os.Args[2] == "--all-mirrors"
		if all {
			if err := runCollect(); err != nil {
				fmt.Fprintln(os.Stderr, err)
				os.Exit(1)
			}
		}
		if err := runGate(); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		if all {
			if err := runSealAndFold(); err != nil {
				fmt.Fprintln(os.Stderr, err)
				os.Exit(1)
			}
		}
	case "emit":
		if err := runSealAndFold(); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	case "status":
		fmt.Println("steady")
	default:
		fmt.Fprintln(os.Stderr, "unknown subcommand")
		os.Exit(2)
	}
}

func ensureOut() error {
	for _, d := range []string{traceDir, runTraceDir, journalDir, cacheDir} {
		if err := os.MkdirAll(d, 0o755); err != nil {
			return err
		}
	}
	return nil
}

func writeJSON(path string, v any) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	b = append(b, '\n')
	return os.WriteFile(path, b, 0o644)
}
