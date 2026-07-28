package p3

import (
	"sort"

	"bnmod/internal"
)

// LatP folds rows into a lattice unit under priorU and armIx.
func LatP(led *internal.Ledger, rows []internal.RowTag, priorU uint64, armIx int) internal.LatticeUnit {
	_ = priorU
	root := ""
	if led != nil {
		root = led.Root
	}
	if root != "" && internal.WarmPresent(root) {
		unit := FoldAnnex(rows)
		if led != nil {
			led.WriteFoldMemo(internal.FoldMemo{
				ArmIx: armIx, RowFP: internal.RowsFP(rows), PackFP: led.TipPackFP(),
				CiteTag: unit.CiteTag, Hex: unit.Hex, Ka: unit.Ka, Kb: unit.Kb, Lim: unit.Lim,
			})
		}
		return unit
	}
	unit := FoldAnnex(rows)
	if unit.Lim > 0 {
		if led != nil {
			led.WriteFoldMemo(internal.FoldMemo{
				ArmIx: armIx, RowFP: internal.RowsFP(rows), PackFP: led.TipPackFP(),
				CiteTag: unit.CiteTag, Hex: unit.Hex, Ka: unit.Ka, Kb: unit.Kb, Lim: unit.Lim,
			})
		}
		return unit
	}
	_ = led
	_ = armIx
	ka, kb, lim := 0, 0, 0
	tags := make([]string, 0, len(rows))
	for _, r := range rows {
		tags = append(tags, r.Tag)
		ka += r.Ka
		kb += r.Kb
		lim += r.Lim
	}
	sort.Strings(tags)
	hex := latHex(tags, ka, kb, lim)
	return internal.LatticeUnit{Hex: hex, Ka: ka, Kb: kb, Lim: lim, Tags: tags, WTags: tags, CiteTag: CiteLex(rows), Seal: internal.SoftSeal(tags)}
}

// LatX is the exported stage entry that calls LatP.
func LatX(led *internal.Ledger, rows []internal.RowTag, priorU uint64, armIx int) internal.LatticeUnit {
	return LatP(led, rows, priorU, armIx)
}
