// Package legacy keeps the pre-1.0 flattener that `slate audit` still uses for
// its closure estimate. It walks edges by name only: ranges, features, yanked
// markers and overrides are all ignored, so its answer is an upper bound on the
// package count and never a lock.
package legacy

import (
	"sort"

	"slate/internal/registry"
)

// FlatClosure lists every package reachable from roots, using the newest
// release of each package to expand edges. The result is sorted ascending.
func FlatClosure(idx *registry.Index, roots []string) []string {
	seen := map[string]bool{}
	queue := append([]string{}, roots...)
	for len(queue) > 0 {
		name := queue[0]
		queue = queue[1:]
		if seen[name] {
			continue
		}
		seen[name] = true
		releases := idx.Releases(name)
		if len(releases) == 0 {
			continue
		}
		newest := releases[0]
		for _, req := range newest.Requires {
			if !seen[req.Name] {
				queue = append(queue, req.Name)
			}
		}
		for _, feat := range newest.FeatureNames() {
			for _, req := range newest.Features[feat] {
				if !seen[req.Name] {
					queue = append(queue, req.Name)
				}
			}
		}
	}
	out := make([]string, 0, len(seen))
	for name := range seen {
		out = append(out, name)
	}
	sort.Strings(out)
	return out
}
