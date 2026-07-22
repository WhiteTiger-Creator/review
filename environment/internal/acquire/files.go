package acquire

import (
	"fmt"
	"os"
	"path/filepath"
)

func writePrivate(path string, data []byte) error {
	if err := os.WriteFile(path, data, 0o640); err != nil {
		return fmt.Errorf("write %s: %w", path, err)
	}
	return nil
}

func ReplaceDirectory(stage, destination string) error {
	if err := os.RemoveAll(destination); err != nil {
		return err
	}
	if err := os.Rename(stage, destination); err != nil {
		return fmt.Errorf("commit evidence directory: %w", err)
	}
	return nil
}

func stageDirectory(destination string) (string, error) {
	parent := filepath.Dir(destination)
	if err := os.MkdirAll(parent, 0o750); err != nil {
		return "", err
	}
	return os.MkdirTemp(parent, ".evidence-stage-")
}
