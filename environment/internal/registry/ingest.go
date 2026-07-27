package registry

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"slate/internal/semver"
)

// Ingest reads every *.json file in dir and validates it against the registry
// format. The returned error is fatal for the caller: a registry that does not
// parse is an input error, not a resolution failure.
func Ingest(dir string) (*Index, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, fmt.Errorf("registry %s: %w", dir, err)
	}
	idx := &Index{packages: map[string]*Package{}, dir: dir}
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".json") {
			continue
		}
		path := filepath.Join(dir, e.Name())
		pkg, err := readPackage(path)
		if err != nil {
			return nil, err
		}
		stem := strings.TrimSuffix(e.Name(), ".json")
		if pkg.Name != stem {
			return nil, fmt.Errorf("registry %s: name %q does not match file stem %q", path, pkg.Name, stem)
		}
		if _, dup := idx.packages[pkg.Name]; dup {
			return nil, fmt.Errorf("registry %s: duplicate package %q", path, pkg.Name)
		}
		idx.packages[pkg.Name] = pkg
	}
	if len(idx.packages) == 0 {
		return nil, fmt.Errorf("registry %s: no package files", dir)
	}
	return idx, nil
}

func readPackage(path string) (*Package, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("registry %s: %w", path, err)
	}
	var pkg Package
	dec := json.NewDecoder(strings.NewReader(string(raw)))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&pkg); err != nil {
		return nil, fmt.Errorf("registry %s: %w", path, err)
	}
	if pkg.Name == "" {
		return nil, fmt.Errorf("registry %s: missing name", path)
	}
	if len(pkg.Releases) == 0 {
		return nil, fmt.Errorf("registry %s: no releases", path)
	}
	seen := map[string]bool{}
	for i := range pkg.Releases {
		rel := &pkg.Releases[i]
		if _, err := semver.Parse(rel.Version); err != nil {
			return nil, fmt.Errorf("registry %s: %w", path, err)
		}
		if seen[rel.Version] {
			return nil, fmt.Errorf("registry %s: duplicate version %s", path, rel.Version)
		}
		seen[rel.Version] = true
		if rel.Requires == nil {
			rel.Requires = []Requirement{}
		}
		for _, req := range rel.Requires {
			if req.Name == "" || req.Range == "" {
				return nil, fmt.Errorf("registry %s: release %s has an empty requirement", path, rel.Version)
			}
		}
		for feat, reqs := range rel.Features {
			if feat == "" {
				return nil, fmt.Errorf("registry %s: release %s has an unnamed feature", path, rel.Version)
			}
			for _, req := range reqs {
				if req.Name == "" || req.Range == "" {
					return nil, fmt.Errorf("registry %s: feature %s of %s has an empty requirement", feat, rel.Version, path)
				}
			}
		}
	}
	// Newest first, so every consumer sees one release order.
	sort.SliceStable(pkg.Releases, func(i, j int) bool {
		return semver.Compare(pkg.Releases[i].Semver(), pkg.Releases[j].Semver()) > 0
	})
	return &pkg, nil
}

func sortStrings(s []string) { sort.Strings(s) }
