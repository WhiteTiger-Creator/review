package r2

import (
	"encoding/json"
	"os"
	"sort"
)

// SortKeys returns map keys sorted for stable debug dumps.
func SortKeys(m map[string]any) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}

// WriteJSON writes raw JSON bytes to path (shared emit primitive).
func WriteJSON(path string, v any) error {
	b, err := json.Marshal(v)
	if err != nil {
		return err
	}
	return os.WriteFile(path, b, 0o644)
}
