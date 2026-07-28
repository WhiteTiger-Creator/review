package report

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

type Artifact struct {
	Path  string
	Value any
}

func WriteAtomic(artifacts []Artifact) error {
	temps := make([]string, 0, len(artifacts))
	for _, artifact := range artifacts {
		if err := os.MkdirAll(filepath.Dir(artifact.Path), 0o755); err != nil {
			cleanup(temps)
			return err
		}
		raw, err := json.MarshalIndent(artifact.Value, "", "  ")
		if err != nil {
			cleanup(temps)
			return err
		}
		raw = append(raw, '\n')
		temp := artifact.Path + ".tmp"
		if err := os.WriteFile(temp, raw, 0o644); err != nil {
			cleanup(append(temps, temp))
			return err
		}
		temps = append(temps, temp)
	}
	for index, artifact := range artifacts {
		if err := os.Rename(temps[index], artifact.Path); err != nil {
			cleanup(temps[index:])
			return fmt.Errorf("replace %s: %w", artifact.Path, err)
		}
	}
	return nil
}

func cleanup(paths []string) {
	for _, path := range paths {
		_ = os.Remove(path)
	}
}
