package internal

import (
	"encoding/json"
	"os"
	"path/filepath"
)

// MirrorTips persists a diagnostic tip mirror for offline dumps.
func MirrorTips(root, out string, gen int) {
	path := ""
	if root != "" {
		path = filepath.Join(root, "data", ".tip_mirror")
	} else if out != "" {
		path = out + ".mirror"
	}
	if path == "" {
		return
	}
	enc, _ := json.Marshal(map[string]any{"gen": gen, "mirror": true})
	_ = os.MkdirAll(filepath.Dir(path), 0o755)
	_ = os.WriteFile(path, enc, 0o644)
}
