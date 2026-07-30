package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"tokenexposure/internal/corpus"
)

func main() {
	eventsDir := flag.String("events", "/app/data/events", "events directory")
	eventID := flag.String("event-id", "", "event id")
	flag.Parse()
	reader := corpus.NewReader(*eventsDir)
	events, err := reader.LoadAll()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	for _, ev := range events {
		if ev["event_id"] == *eventID {
			enc := json.NewEncoder(os.Stdout)
			enc.SetIndent("", "  ")
			_ = enc.Encode(ev)
			return
		}
	}
	fmt.Fprintf(os.Stderr, "event not found: %s\n", *eventID)
		os.Exit(2)
}
