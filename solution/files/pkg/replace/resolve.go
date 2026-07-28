package replace

import (
	"fmt"
	"sort"
	"strings"

	"bsplan/pkg/load"
)

type Resolver struct {
	entries []load.Replace
}

func New(entries []load.Replace) (Resolver, error) {
	copyEntries := append([]load.Replace{}, entries...)
	seen := map[string]bool{}
	for _, entry := range copyEntries {
		if strings.TrimSpace(entry.Old) == "" || strings.TrimSpace(entry.New) == "" {
			return Resolver{}, fmt.Errorf("replacement paths must be non-empty")
		}
		if seen[entry.Old] {
			return Resolver{}, fmt.Errorf("duplicate replacement source %q", entry.Old)
		}
		seen[entry.Old] = true
	}
	sort.Slice(copyEntries, func(i, j int) bool {
		if len(copyEntries[i].Old) != len(copyEntries[j].Old) {
			return len(copyEntries[i].Old) > len(copyEntries[j].Old)
		}
		return copyEntries[i].Old < copyEntries[j].Old
	})
	return Resolver{entries: copyEntries}, nil
}

func (r Resolver) Resolve(path string) (string, error) {
	current := path
	seen := map[string]bool{current: true}
	for step := 0; step <= len(r.entries); step++ {
		next, matched := r.rewriteOnce(current)
		if !matched {
			return current, nil
		}
		if seen[next] {
			return "", fmt.Errorf("replacement cycle while resolving %q", path)
		}
		seen[next] = true
		current = next
	}
	return "", fmt.Errorf("replacement chain did not converge for %q", path)
}

func (r Resolver) rewriteOnce(path string) (string, bool) {
	for _, entry := range r.entries {
		if path == entry.Old {
			return entry.New, true
		}
		if strings.HasPrefix(path, entry.Old+"/") {
			return entry.New + strings.TrimPrefix(path, entry.Old), true
		}
	}
	return path, false
}
