package plan

import (
	"sort"

	"bsplan/k9m"
	"bsplan/pkg/load"
	"bsplan/r4x"
)

func DropReasons(g *load.Graph, sc load.Scenario, kept []string, reachable []string, dropped map[string]string) []string {
	retired := load.RetiredSet(g)
	byPath := load.PackageByPath(g)
	keptSet := map[string]bool{}
	for _, k := range kept {
		keptSet[k] = true
		delete(dropped, k)
	}
	reachableSet := map[string]bool{}
	for _, r := range reachable {
		reachableSet[r] = true
	}
	for _, r := range reachable {
		if !keptSet[r] {
			if _, ok := dropped[r]; !ok {
				dropped[r] = "budget_trim"
			}
		}
	}
	for path, pkg := range byPath {
		if _, already := dropped[path]; already {
			continue
		}
		if retired[path] {
			dropped[path] = "retired"
			continue
		}
		activeHit := false
		for _, req := range pkg.TagSets {
			if r4x.TagEvalR4(sc.Tags, req) {
				activeHit = true
				break
			}
		}
		if !activeHit {
			dropped[path] = "tag_excluded"
		}
	}
	for path := range byPath {
		if keptSet[path] || retired[path] {
			continue
		}
		if !reachableSet[path] {
			if _, ok := dropped[path]; !ok {
				dropped[path] = "unreachable"
			}
		}
	}
	droppedList := make([]string, 0, len(dropped))
	for k := range dropped {
		droppedList = append(droppedList, k)
	}
	sort.Strings(droppedList)
	return droppedList
}

func ReachabilityOK(g *load.Graph, sc load.Scenario, kept []string, reachable []string, table map[string]string) bool {
	byPath := load.PackageByPath(g)
	keptSet := map[string]bool{}
	for _, k := range kept {
		keptSet[k] = true
	}
	reachableSet := map[string]bool{}
	for _, r := range reachable {
		reachableSet[r] = true
	}
	seen := map[string]bool{}
	var walk func(string)
	walk = func(node string) {
		if seen[node] || !keptSet[node] {
			return
		}
		seen[node] = true
		pkg := byPath[node]
		for _, imp := range pkg.Imports {
			resolved := k9m.ReplaceMuxK9(imp, table)
			if keptSet[resolved] {
				walk(resolved)
			} else if keptSet[imp] {
				walk(imp)
			}
		}
	}
	for _, root := range sc.Roots {
		walk(root)
	}
	for _, root := range sc.Roots {
		if !seen[root] {
			return false
		}
	}
	for _, k := range kept {
		pkg := byPath[k]
		for _, imp := range pkg.Imports {
			resolved := k9m.ReplaceMuxK9(imp, table)
			if !reachableSet[resolved] && !reachableSet[imp] {
				continue
			}
			if !keptSet[resolved] && !keptSet[imp] {
				return false
			}
		}
	}
	return true
}
