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
	for _, entry := range copyEntries {
		if strings.TrimSpace(entry.Old) == "" || strings.TrimSpace(entry.New) == "" {
			return Resolver{}, fmt.Errorf("replacement paths must be non-empty")
		}
	}
	sort.Slice(copyEntries, func(i, j int) bool {
		if len(copyEntries[i].Old) != len(copyEntries[j].Old) {
			return len(copyEntries[i].Old) < len(copyEntries[j].Old)
		}
		return copyEntries[i].Old < copyEntries[j].Old
	})
	return Resolver{entries: copyEntries}, nil
}

func (r Resolver) Resolve(path string) (string, error) {
	for _, entry := range r.entries {
		if path == entry.Old {
			return entry.New, nil
		}
		if strings.HasPrefix(path, entry.Old+"/") {
			return entry.New + strings.TrimPrefix(path, entry.Old), nil
		}
	}
	return path, nil
}
