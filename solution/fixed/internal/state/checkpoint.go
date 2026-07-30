package state

import (
	"encoding/json"
	"os"
)

type Checkpoint struct {
	Path string
}

func (c *Checkpoint) Load() (map[string]any, error) {
	b, err := os.ReadFile(c.Path)
	if err != nil {
		return map[string]any{"status": "DISCOVERING"}, nil
	}
	var st map[string]any
	if err := json.Unmarshal(b, &st); err != nil {
		return nil, err
	}
	return st, nil
}

func (c *Checkpoint) Save(st map[string]any) error {
	b, err := json.MarshalIndent(st, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(c.Path, append(b, '\n'), 0o644)
}
