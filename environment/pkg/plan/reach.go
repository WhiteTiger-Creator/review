package plan

import (
	"sort"

	"bsplan/k9m"
	"bsplan/pkg/load"
)

func Reachable(g *load.Graph, active map[string]load.Package, roots []string, table map[string]string) []string {
	seen := map[string]bool{}
	var walk func(string)
	walk = func(path string) {
		resolved := k9m.ReplaceMuxK9(path, table)
		if seen[resolved] {
			return
		}
		pkg, ok := active[resolved]
		if !ok {
			if pkg2, ok2 := active[path]; ok2 {
				pkg = pkg2
				resolved = path
			} else {
				return
			}
		}
		seen[resolved] = true
		for _, imp := range pkg.Imports {
			walk(imp)
		}
	}
	for _, root := range roots {
		walk(root)
	}
	out := make([]string, 0, len(seen))
	for k := range seen {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}
