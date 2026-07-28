package ocneval

import (
	"bnmod/internal"
	"bnmod/pipe/p12"
)

func init() {
	p12.AfterScore = ApplyA
}

// ApplyA is the post-score pipe adapter.
func ApplyA(led *internal.Ledger, rows []internal.RowTag, armIx int) []internal.RowTag {
	_ = armIx
	if led != nil && led.Root != "" {
		internal.WriteRowCache(led.Root, rows)
	}
	return rows
}
