package report

import (
	"sort"

	"github.com/local/etaengine/types"
)

func sortRuns(runs []types.RunRec) []types.RunRec {
	cp := make([]types.RunRec, len(runs))
	copy(cp, runs)
	sort.SliceStable(cp, func(i, j int) bool {
		if cp[i].Family == cp[j].Family {
			if cp[i].InstanceID == cp[j].InstanceID {
				return cp[i].Seed < cp[j].Seed
			}
			return cp[i].InstanceID < cp[j].InstanceID
		}
		return cp[i].Family < cp[j].Family
	})
	return cp
}

func familyList(runs []types.RunRec) []string {
	famSet := map[string]struct{}{}
	for _, r := range runs {
		if r.Family == "" {
			continue
		}
		famSet[r.Family] = struct{}{}
	}
	fams := make([]string, 0, len(famSet))
	for f := range famSet {
		fams = append(fams, f)
	}
	sort.Strings(fams)
	return fams
}

func BuildD0(runs []types.RunRec, generation uint64, modelID string) types.OutDoc {
	cp := sortRuns(runs)
	var doc types.OutDoc
	doc.Version = 1
	doc.Runs = cp
	doc.Summary.InstanceCount = len(cp)
	doc.Summary.Families = familyList(cp)
	doc.Summary.Generation = generation
	doc.Summary.ModelID = modelID
	return doc
}
