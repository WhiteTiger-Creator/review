// Package canon writes the byte shape every Slate artifact shares: UTF-8 JSON,
// two-space indent, no HTML escaping, exactly one trailing newline.
package canon

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

// Marshal renders v in the canonical byte shape.
func Marshal(v interface{}) ([]byte, error) {
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	enc.SetIndent("", "  ")
	if err := enc.Encode(v); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}

// Write renders v and writes it to path, creating parent directories.
func Write(path string, v interface{}) error {
	data, err := Marshal(v)
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return fmt.Errorf("canon %s: %w", path, err)
	}
	if err := os.WriteFile(path, data, 0o644); err != nil {
		return fmt.Errorf("canon %s: %w", path, err)
	}
	return nil
}
