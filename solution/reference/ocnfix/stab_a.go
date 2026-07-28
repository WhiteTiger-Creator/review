package ocnfix

import (
	"bnmod/internal"
	"bnmod/pipe/p12"
)

func init() {
	p12.AfterScore = StabilizeRows
}

// StabilizeRows is the post-score stabilization hook.
func StabilizeRows(led *internal.Ledger, rows []internal.RowTag, armIx int) []internal.RowTag {
	_ = led
	_ = armIx
	return rows
}
