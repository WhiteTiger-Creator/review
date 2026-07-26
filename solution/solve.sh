#!/bin/bash
set -euo pipefail
cd /app/environment

cat > r4x/tag_r4.go <<'EOF'
package r4x

import "strings"

func TagEvalR4(active []string, required []string) bool {
	present := map[string]bool{}
	forbidden := map[string]bool{}
	for _, t := range active {
		if strings.HasPrefix(t, "!") {
			forbidden[t[1:]] = true
			continue
		}
		present[t] = true
	}
	for _, req := range required {
		if strings.HasPrefix(req, "!") {
			name := req[1:]
			if present[name] {
				return false
			}
		} else if !present[req] {
			return false
		}
	}
	for name := range forbidden {
		if present[name] {
			return false
		}
	}
	return true
}
EOF

cat > k9m/rep_k9.go <<'EOF'
package k9m

import "strings"

func ReplaceMuxK9(path string, table map[string]string) string {
	bestOld := ""
	bestNew := ""
	for old, neu := range table {
		if path == old || strings.HasPrefix(path, old+"/") {
			if len(old) > len(bestOld) {
				bestOld = old
				bestNew = neu
			}
		}
	}
	if bestOld == "" {
		return path
	}
	if path == bestOld {
		return bestNew
	}
	suffix := strings.TrimPrefix(path, bestOld)
	return bestNew + suffix
}
EOF

cat > n2p/prn_n2.go <<'EOF'
package n2p

import (
	"sort"

	"bsplan/k9m"
)

func rootsReachable(kept map[string]bool, roots []string, edges map[string][]string, reachable []string, table map[string]string) bool {
	reachableSet := map[string]bool{}
	for _, pkg := range reachable {
		reachableSet[pkg] = true
	}
	seen := map[string]bool{}
	var walk func(string)
	walk = func(cur string) {
		if seen[cur] || !kept[cur] {
			return
		}
		seen[cur] = true
		for _, imp := range edges[cur] {
			resolved := k9m.ReplaceMuxK9(imp, table)
			if kept[resolved] {
				walk(resolved)
			} else if kept[imp] {
				walk(imp)
			}
		}
	}
	for _, root := range roots {
		walk(root)
	}
	for _, root := range roots {
		if !seen[root] {
			return false
		}
	}
	for pkg := range kept {
		for _, imp := range edges[pkg] {
			resolved := k9m.ReplaceMuxK9(imp, table)
			if reachableSet[resolved] && !kept[resolved] {
				return false
			}
			if reachableSet[imp] && !kept[imp] && !kept[resolved] {
				return false
			}
		}
	}
	return true
}

func PruneSelN2(reachable []string, optional map[string]bool, ceiling int, roots []string, edges map[string][]string, table map[string]string) ([]string, map[string]string) {
	kept := map[string]bool{}
	for _, pkg := range reachable {
		kept[pkg] = true
	}
	rootSet := map[string]bool{}
	for _, root := range roots {
		rootSet[root] = true
	}

	order := append([]string{}, reachable...)
	sort.Slice(order, func(i, j int) bool {
		oi := optional[order[i]]
		oj := optional[order[j]]
		if oi != oj {
			return oi && !oj
		}
		return order[i] < order[j]
	})

	changed := true
	for changed {
		changed = false
		for _, pkg := range order {
			if !kept[pkg] || rootSet[pkg] {
				continue
			}
			kept[pkg] = false
			if rootsReachable(kept, roots, edges, reachable, table) {
				changed = true
			} else {
				kept[pkg] = true
			}
		}
	}

	for countTrue(kept) > ceiling {
		trimmed := false
		for _, pkg := range order {
			if !kept[pkg] || rootSet[pkg] {
				continue
			}
			kept[pkg] = false
			if rootsReachable(kept, roots, edges, reachable, table) && countTrue(kept) <= ceiling {
				trimmed = true
				break
			}
			kept[pkg] = true
		}
		if !trimmed {
			break
		}
	}

	dropped := map[string]string{}
	var keptList []string
	for _, pkg := range reachable {
		if kept[pkg] {
			keptList = append(keptList, pkg)
		} else {
			dropped[pkg] = "budget_trim"
		}
	}
	sort.Strings(keptList)
	return keptList, dropped
}

func countTrue(m map[string]bool) int {
	n := 0
	for _, v := range m {
		if v {
			n++
		}
	}
	return n
}
EOF

go run ./cmd/slice --all-scenarios --write /app/output/buildslice_report.json
