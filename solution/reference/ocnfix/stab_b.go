package ocnfix

import (
	"bnmod/internal"
	"bnmod/pipe/p12"
)

func init() {
	p12.AfterFold = StabilizeUnit
}

// StabilizeUnit is the post-fold stabilization hook.
func StabilizeUnit(unit internal.LatticeUnit, rows []internal.RowTag) internal.LatticeUnit {
	_ = rows
	return unit
}
