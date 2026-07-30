package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"tokenexposure/internal/corpus"
	"tokenexposure/internal/reduce"
)

func main() {
	eventsDir := flag.String("events", "/app/data/events", "events directory")
	configDir := flag.String("config", "/app/config", "config directory")
	tokenID := flag.String("token-id", "", "stable token id")
	flag.Parse()
	reader := corpus.NewReader(*eventsDir)
	events, err := reader.LoadAll()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	chains, err := reduce.BuildChains(events, *configDir)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	for _, ch := range chains {
		if ch.TokenID == *tokenID {
			enc := json.NewEncoder(os.Stdout)
			enc.SetIndent("", "  ")
			_ = enc.Encode(ch)
			return
		}
	}
	fmt.Fprintf(os.Stderr, "token chain not found: %s\n", *tokenID)
		os.Exit(2)
}
