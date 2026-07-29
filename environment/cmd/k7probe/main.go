package main

import (
	"encoding/json"
	"fmt"
	"os"

	"k7w/internal/wire"
)

func main() {
	if len(os.Args) < 4 || os.Args[1] != "observe" || os.Args[2] != "--chunk" {
		os.Exit(2)
	}
	frame, err := os.ReadFile(os.Args[3])
	if err != nil {
		os.Exit(2)
	}
	stamp, err := wire.CanonStamp(frame)
	if err != nil {
		os.Exit(2)
	}
	body, _ := wire.BodyOf(frame)
	out := map[string]any{"canon_hex": stamp, "body_len": len(body)}
	raw, _ := json.Marshal(out)
	fmt.Println(string(raw))
}
