package ocnfix

import (
	"bnmod/internal"
	"bnmod/p3"
	"bnmod/pipe/p12"
)

func init() {
	p12.AfterFold = StabilizeUnit
}

// StabilizeUnit is the post-fold stabilization hook.
func StabilizeUnit(unit internal.LatticeUnit, rows []internal.RowTag) internal.LatticeUnit {
	if unit.Hex == "" && unit.CiteTag == "" {
		return unit
	}
	unit.CiteTag = p3.CiteLex(rows)
	unit.Seal = internal.SoftSeal(unit.WTags)
	if unit.Seal == "" {
		unit.Seal = internal.SoftSeal(unit.Tags)
	}
	return unit
}
