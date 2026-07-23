package main

import (
	"encoding/json"
	"os"
)

func main() {
	if len(os.Args) != 4 {
		os.Exit(2)
	}
	out := map[string]any{
		"status":   "blocked",
		"packages": []any{},
		"rejected": []map[string]string{{"name": "starter", "reason": "no_lock"}},
	}
	raw, _ := json.Marshal(out)
	_ = os.WriteFile(os.Args[3], raw, 0644)
}
