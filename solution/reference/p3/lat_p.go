package p3

import (
	"sort"

	"bnmod/internal"
)

// LatP folds rows into a lattice unit under priorU and armIx.
func LatP(led *internal.Ledger, rows []internal.RowTag, priorU uint64, armIx int) internal.LatticeUnit {
	_ = priorU
	if rows == nil {
		return internal.LatticeUnit{}
	}
	root := ""
	if led != nil {
		root = led.Root
	}
	if root != "" {
		internal.ClearWarm(root)
	}
	if root != "" && !internal.RedotOK(root, rows) {
		return internal.LatticeUnit{}
	}
	packFP := ""
	if led != nil {
		packFP = led.TipPackFP()
	}
	if led == nil || !led.ExpectPack(armIx, packFP) || !led.ExpectRows(armIx, rows) || !internal.PinOrderOK(root, rows) {
		if led != nil {
			if m, ok := led.ReadFoldMemo(armIx, internal.RowsFP(rows), packFP); ok && m.CiteTag == CitePin(rows) && m.PackFP == packFP && packFP != "" {
				seal := internal.AuthSeal(m.CiteTag)
				if seal == "" || seal != internal.AuthSeal(CitePin(rows)) {
					return internal.LatticeUnit{}
				}
				unit := internal.LatticeUnit{
					Hex: m.Hex, Ka: m.Ka, Kb: m.Kb, Lim: m.Lim,
					CiteTag: m.CiteTag, Seal: seal, PackFP: m.PackFP,
				}
				led.CommitLat(armIx, unit)
				return unit
			}
		}
		return internal.LatticeUnit{}
	}
	ka, kb, lim := 0, 0, 0
	tags := make([]string, 0, len(rows))
	wtags := make([]string, 0, len(rows))
	for _, r := range rows {
		if r.Tag == "" {
			continue
		}
		tags = append(tags, r.Tag)
		if r.Role != 0 {
			continue
		}
		if r.Lim < 0 {
			continue
		}
		wtags = append(wtags, r.Tag)
		ka += r.Ka
		kb += r.Kb
		lim += r.Lim
	}
	if lim < 0 {
		lim = 0
	}
	if ka < 0 {
		ka = 0
	}
	if kb < 0 {
		kb = 0
	}
	cite := CitePin(rows)
	if cite == "" {
		return internal.LatticeUnit{}
	}
	seal := internal.AuthSeal(cite)
	if seal == "" {
		return internal.LatticeUnit{}
	}
	sort.Strings(tags)
	wsorted := append([]string(nil), wtags...)
	sort.Strings(wsorted)
	hex := latHex(wsorted, ka, kb, lim)
	unit := internal.LatticeUnit{
		Hex: hex, Ka: ka, Kb: kb, Lim: lim, Tags: tags, WTags: wtags,
		CiteTag: cite, Seal: seal, PackFP: packFP,
	}
	led.CommitLat(armIx, unit)
	led.WriteFoldMemo(internal.FoldMemo{
		ArmIx: armIx, RowFP: internal.RowsFP(rows), PackFP: packFP,
		CiteTag: cite, Hex: hex, Ka: ka, Kb: kb, Lim: lim,
	})
	return unit
}

// LatX is the exported stage entry that calls LatP.
func LatX(led *internal.Ledger, rows []internal.RowTag, priorU uint64, armIx int) internal.LatticeUnit {
	if rows == nil {
		return internal.LatticeUnit{}
	}
	return LatP(led, rows, priorU, armIx)
}
