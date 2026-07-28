package internal

import (
	"os"
	"path/filepath"
)

const warmName = "shadow_warm.bin"
const rowCacheName = "row_scores.bin"

// WarmPath is the training-window short-circuit marker under data/.
func WarmPath(root string) string {
	return filepath.Join(root, "data", warmName)
}

// WarmPresent reports whether the warm marker exists.
func WarmPresent(root string) bool {
	_, err := os.Stat(WarmPath(root))
	return err == nil
}

// WriteWarm creates the warm short-circuit marker.
func WriteWarm(root string) {
	if root == "" {
		return
	}
	_ = os.MkdirAll(filepath.Join(root, "data"), 0o755)
	_ = os.WriteFile(WarmPath(root), []byte("warm\n"), 0o644)
}

// ClearWarm removes the warm marker and scored-row residue.
func ClearWarm(root string) {
	if root == "" {
		return
	}
	_ = os.Remove(WarmPath(root))
	_ = os.Remove(filepath.Join(root, "data", rowCacheName))
}
