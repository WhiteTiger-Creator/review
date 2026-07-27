package integrity

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

type Manifest struct {
	Version string            `json:"version"`
	Files   map[string]string `json:"files"`
}

func HashFile(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

func BuildManifest(root string, relPaths []string) (Manifest, error) {
	m := Manifest{Version: "1.0", Files: map[string]string{}}
	sort.Strings(relPaths)
	for _, rel := range relPaths {
		sum, err := HashFile(filepath.Join(root, rel))
		if err != nil {
			return m, err
		}
		m.Files[filepath.ToSlash(rel)] = sum
	}
	return m, nil
}

func WriteManifest(path string, m Manifest) error {
	b, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		return err
	}
	b = append(b, '\n')
	return os.WriteFile(path, b, 0o644)
}

func LoadManifest(path string) (Manifest, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return Manifest{}, err
	}
	var m Manifest
	if err := json.Unmarshal(b, &m); err != nil {
		return Manifest{}, err
	}
	return m, nil
}

func Verify(root string, m Manifest) error {
	keys := make([]string, 0, len(m.Files))
	for k := range m.Files {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, rel := range keys {
		sum, err := HashFile(filepath.Join(root, rel))
		if err != nil {
			return fmt.Errorf("integrity missing %s: %w", rel, err)
		}
		if !strings.EqualFold(sum, m.Files[rel]) {
			return fmt.Errorf("integrity mismatch for %s", rel)
		}
	}
	return nil
}

func CollectRelPaths(root string, prefixes ...string) ([]string, error) {
	var out []string
	err := filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if info.IsDir() {
			return nil
		}
		rel, err := filepath.Rel(root, path)
		if err != nil {
			return err
		}
		rel = filepath.ToSlash(rel)
		if strings.HasPrefix(rel, "integrity/") {
			return nil
		}
		if len(prefixes) == 0 {
			out = append(out, rel)
			return nil
		}
		for _, p := range prefixes {
			if strings.HasPrefix(rel, p) {
				out = append(out, rel)
				break
			}
		}
		return nil
	})
	return out, err
}
