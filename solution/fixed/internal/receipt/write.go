package receipt

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"beaconaudit/internal/model"
)

func ValidateDestination(path, evidenceDirectory string) error {
	absolute, err := filepath.Abs(path)
	if err != nil {
		return err
	}
	evidence, err := filepath.Abs(evidenceDirectory)
	if err != nil {
		return err
	}
	relative, err := filepath.Rel(evidence, absolute)
	if err != nil {
		return err
	}
	if relative == "." || (relative != ".." && !strings.HasPrefix(relative, ".."+string(filepath.Separator))) {
		return fmt.Errorf("receipt must be outside the evidence directory")
	}
	parent := filepath.Dir(absolute)
	resolved, err := filepath.EvalSymlinks(parent)
	if err != nil || resolved != filepath.Clean(parent) {
		return fmt.Errorf("receipt parent must be an existing directory without symbolic links")
	}
	info, err := os.Lstat(parent)
	if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return fmt.Errorf("receipt parent must be an existing directory without symbolic links")
	}
	if info, err := os.Lstat(absolute); err == nil {
		if !info.Mode().IsRegular() || info.Mode()&os.ModeSymlink != 0 {
			return fmt.Errorf("receipt destination is not a regular file")
		}
	} else if !os.IsNotExist(err) {
		return err
	}
	return nil
}

func Write(path string, value model.Receipt) error {
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	if err := os.MkdirAll(filepath.Dir(path), 0o750); err != nil {
		return err
	}
	temporary, err := os.CreateTemp(filepath.Dir(path), ".receipt-")
	if err != nil {
		return err
	}
	temporaryName := temporary.Name()
	defer os.Remove(temporaryName)
	if err := temporary.Chmod(0o640); err != nil {
		temporary.Close()
		return err
	}
	if _, err := temporary.Write(data); err != nil {
		temporary.Close()
		return err
	}
	if err := temporary.Sync(); err != nil {
		temporary.Close()
		return err
	}
	if err := temporary.Close(); err != nil {
		return err
	}
	if err := os.Rename(temporaryName, path); err != nil {
		return fmt.Errorf("commit receipt: %w", err)
	}
	return nil
}
