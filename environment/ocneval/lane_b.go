package ocneval

import (
	"bnmod/internal"
	"bnmod/pipe/p12"
)

func init() {
	p12.AfterFold = ApplyB
}

// ApplyB is the post-fold pipe adapter.
func ApplyB(unit internal.LatticeUnit, rows []internal.RowTag) internal.LatticeUnit {
	_ = rows
	return unit
}
