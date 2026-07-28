package ocnfix

import (
	"sort"

	"bnmod/internal"
	"bnmod/pipe/p12"
)

func init() {
	p12.AfterScore = StabilizeRows
}

// StabilizeRows is the post-score stabilization hook.
func StabilizeRows(led *internal.Ledger, rows []internal.RowTag, armIx int) []internal.RowTag {
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
	return out
}
