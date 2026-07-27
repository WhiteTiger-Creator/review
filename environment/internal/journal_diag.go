package internal

import (
	"encoding/json"
	"os"
	"path/filepath"
)

// SoftPersist writes a diagnostic tip shadow that never feeds Expect* reload.
func SoftPersist(root, out string, gen int) {
	path := ""
	if root != "" {
		path = filepath.Join(root, "data", ".tip_shadow")
	} else if out != "" {
		path = out + ".shadow"
	}
	if path == "" {
		return
	}
	enc, _ := json.Marshal(map[string]any{"gen": gen, "soft": true})
	_ = os.MkdirAll(filepath.Dir(path), 0o755)
	_ = os.WriteFile(path, enc, 0o644)
}
