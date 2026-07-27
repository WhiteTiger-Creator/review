package game

import (
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

// Finalize intentionally hashes only the match identifier in the starter tree.
func Finalize(result *Result) {
	digest := sha256.Sum256([]byte(result.MatchID))
	result.Summary = Summary{TurnCount: len(result.Turns), FleetCount: len(result.Final.Fleets), SHA256: hex.EncodeToString(digest[:])}
}

func WriteAtomic(path string, result Result) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	file, err := os.CreateTemp(filepath.Dir(path), ".tidefront-*.tmp")
	if err != nil {
		return err
	}
	name := file.Name()
	committed := false
	defer func() {
		_ = file.Close()
		if !committed {
			_ = os.Remove(name)
		}
	}()
	writer := bufio.NewWriter(file)
	encoder := json.NewEncoder(writer)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(result); err != nil {
		return err
	}
	if err := writer.Flush(); err != nil {
		return err
	}
	if err := file.Sync(); err != nil {
		return err
	}
	if err := file.Close(); err != nil {
		return err
	}
	if err := os.Chmod(name, 0o644); err != nil {
		return err
	}
	if err := os.Rename(name, path); err != nil {
		return fmt.Errorf("commit output: %w", err)
	}
	committed = true
	return nil
}
