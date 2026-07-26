package plan

import (
	"bsplan/pkg/load"
	"bsplan/r4x"
)

func ActivePackages(g *load.Graph, tags []string) map[string]load.Package {
	active := map[string]load.Package{}
	retired := load.RetiredSet(g)
	for _, p := range g.Packages {
		if retired[p.ImportPath] {
			continue
		}
		for _, req := range p.TagSets {
			if r4x.TagEvalR4(tags, req) {
				active[p.ImportPath] = p
				break
			}
		}
	}
	return active
}
