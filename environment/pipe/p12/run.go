package p12

import (
	"bnmod/internal"
	"bnmod/n7"
	"bnmod/p3"
)

// Bundle carries scored rows and one lattice unit for an arm.
type Bundle struct {
	Rows []internal.RowTag
	Unit internal.LatticeUnit
}

// Run scores then folds for one arm index and seed under a shared ledger.
func Run(led *internal.Ledger, root string, seed uint64, armIx int) Bundle {
	if led != nil && led.Root == "" {
		led.Root = root
	}
	rows := n7.ScrX(led, root, seed, armIx)
	if AfterScore != nil {
		rows = AfterScore(led, rows, armIx)
	}
	unit := p3.LatX(led, rows, seed, armIx)
	if AfterFold != nil {
		unit = AfterFold(unit, rows)
	}
	if led == nil || !led.ExpectPack(armIx, led.TipPackFP()) || !led.ExpectRows(armIx, rows) || !led.ExpectLat(armIx, unit) {
		return Bundle{Rows: rows}
	}
	if unit.CiteTag == "" || unit.Seal == "" || unit.Seal != internal.AuthSeal(unit.CiteTag) {
		return Bundle{Rows: rows}
	}
	if !internal.RedotOK(root, rows) {
		return Bundle{Rows: rows}
	}
	return Bundle{Rows: rows, Unit: unit}
}
