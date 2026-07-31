package scene

import (
	"encoding/json"
	"os"
	"path/filepath"
)

func LoadBundle(root string) (Bundle, error) {
	var b Bundle
	raw, err := os.ReadFile(filepath.Join(root, "data", "bundle.json"))
	if err != nil {
		return b, err
	}
	err = json.Unmarshal(raw, &b)
	return b, err
}

func LoadCase(root, id string) (Case, error) {
	var c Case
	raw, err := os.ReadFile(filepath.Join(root, "data", "cases", id, "case.json"))
	if err != nil {
		return c, err
	}
	err = json.Unmarshal(raw, &c)
	if c.ID == "" {
		c.ID = id
	}
	return c, err
}
