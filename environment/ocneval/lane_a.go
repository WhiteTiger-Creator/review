package ocneval

import (
	"sort"

	"bnmod/internal"
	"bnmod/pipe/p12"
)

func init() {
	p12.AfterScore = ApplyA
}

// ApplyA is the post-score pipe adapter.
func ApplyA(led *internal.Ledger, rows []internal.RowTag, armIx int) []internal.RowTag {
	if len(rows) == 0 {
		return rows
	}
	out := append([]internal.RowTag(nil), rows...)
	sort.SliceStable(out, func(i, j int) bool {
		if out[i].Tag == out[j].Tag {
			return out[i].Ix < out[j].Ix
		}
		return out[i].Tag < out[j].Tag
	})
	if led != nil {
		led.CommitRows(armIx, out)
	}
	root := ""
	if led != nil {
		root = led.Root
	}
	internal.WriteRowCache(root, out)
	return out
}
