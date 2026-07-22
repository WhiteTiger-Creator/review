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
	if err := safeDirectoryPath(filepath.Dir(destination)); err != nil {
		return err
	}
	backup := ""
	if info, err := os.Lstat(destination); err == nil {
		if !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
			return fmt.Errorf("evidence destination is not a safe directory")
		}
		backup = destination + ".previous"
		if _, err := os.Lstat(backup); !os.IsNotExist(err) {
			return fmt.Errorf("evidence backup path already exists")
		}
		if err := os.Rename(destination, backup); err != nil {
			return fmt.Errorf("stage previous evidence directory: %w", err)
		}
	} else if !os.IsNotExist(err) {
		return err
	}
	if err := os.Rename(stage, destination); err != nil {
		if backup != "" {
			_ = os.Rename(backup, destination)
		}
		return fmt.Errorf("commit evidence directory: %w", err)
	}
	if backup != "" {
		if err := os.RemoveAll(backup); err != nil {
			return fmt.Errorf("remove previous evidence directory: %w", err)
		}
	}
	return nil
}

func stageDirectory(destination string) (string, error) {
	parent := filepath.Dir(destination)
	if err := os.MkdirAll(parent, 0o750); err != nil {
		return "", err
	}
	if err := safeDirectoryPath(parent); err != nil {
		return "", err
	}
	if info, err := os.Lstat(destination); err == nil && (!info.IsDir() || info.Mode()&os.ModeSymlink != 0) {
		return "", fmt.Errorf("evidence destination is not a safe directory")
	} else if err != nil && !os.IsNotExist(err) {
		return "", err
	}
	return os.MkdirTemp(parent, ".evidence-stage-")
}

func safeDirectoryPath(path string) error {
	clean := filepath.Clean(path)
	resolved, err := filepath.EvalSymlinks(clean)
	if err != nil {
		return fmt.Errorf("inspect evidence parent: %w", err)
	}
	if resolved != clean {
		return fmt.Errorf("evidence parent must not traverse symbolic links")
	}
	info, err := os.Lstat(clean)
	if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return fmt.Errorf("evidence parent is not a safe directory")
	}
	return nil
}
