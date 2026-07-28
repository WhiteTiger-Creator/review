package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"tidefront.local/game/internal/catalog"
	"tidefront.local/game/internal/game"
	"tidefront.local/game/internal/model"
	"tidefront.local/game/internal/strictjson"
	"tidefront.local/game/internal/timebridge"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, "tidefront:", err)
		os.Exit(2)
	}
}

func run() error {
	if len(os.Args) < 2 || os.Args[1] != "adjudicate" {
		return fmt.Errorf("usage: tidefront adjudicate [options]")
	}
	fs := flag.NewFlagSet("adjudicate", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)
	matchPath := fs.String("match", "", "match JSON")
	stationsPath := fs.String("stations", "", "station bundle JSON")
	catalogPath := fs.String("catalog", "", "constituent catalog directory")
	leapsPath := fs.String("leaps", "", "leap table")
	threads := fs.Int("threads", 1, "worker count")
	outputPath := fs.String("output", "", "result JSON")
	if err := fs.Parse(os.Args[2:]); err != nil {
		return err
	}
	if fs.NArg() != 0 {
		return fmt.Errorf("unexpected positional arguments")
	}
	if *matchPath == "" || *stationsPath == "" || *catalogPath == "" || *leapsPath == "" || *outputPath == "" {
		return fmt.Errorf("match stations catalog leaps and output are required")
	}
	for _, value := range []string{*matchPath, *stationsPath, *catalogPath, *leapsPath, *outputPath} {
		if !filepath.IsAbs(value) {
			return fmt.Errorf("all paths must be absolute")
		}
	}
	_ = os.Remove(*outputPath)
	succeeded := false
	defer func() {
		if !succeeded {
			_ = os.Remove(*outputPath)
		}
	}()
	matchBytes, err := os.ReadFile(*matchPath)
	if err != nil {
		return fmt.Errorf("read match: %w", err)
	}
	var match game.Match
	if err := strictjson.Decode(matchBytes, &match); err != nil {
		return fmt.Errorf("decode match: %w", err)
	}
	stationBytes, err := os.ReadFile(*stationsPath)
	if err != nil {
		return fmt.Errorf("read stations: %w", err)
	}
	var bundle model.Bundle
	if err := strictjson.Decode(stationBytes, &bundle); err != nil {
		return fmt.Errorf("decode stations: %w", err)
	}
	catalogEntries, err := catalog.Load(*catalogPath)
	if err != nil {
		return err
	}
	clock, err := timebridge.Load(*leapsPath)
	if err != nil {
		return fmt.Errorf("load leaps: %w", err)
	}
	defer clock.Close()
	result, err := game.Adjudicate(match, bundle, catalogEntries, clock, *threads)
	if err != nil {
		return err
	}
	if err := game.WriteAtomic(*outputPath, result); err != nil {
		return err
	}
	succeeded = true
	return nil
}
