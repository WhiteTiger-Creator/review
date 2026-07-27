package p34

import (
	"bnmod/internal"
	"bnmod/r2"
	"bnmod/w9"
)

// Run rebinds one arm and writes into the proof log path under a shared ledger.
func Run(led *internal.Ledger, unit internal.LatticeUnit, arms []internal.JumpArm, partIx int, outPath string) internal.ProofDigest {
	if led == nil || unit.CiteTag == "" || !led.ExpectLat(partIx, unit) {
		return internal.ProofDigest{Path: outPath}
	}
	dig := w9.JwX(led, unit, arms, partIx)
	if AfterBind != nil {
		dig = AfterBind(led, dig, unit, arms, partIx)
	}
	if dig.Arm == "" || !led.ExpectJmp(partIx, dig) {
		return internal.ProofDigest{Path: outPath}
	}
	if dig.Cite != unit.CiteTag {
		return internal.ProofDigest{Path: outPath}
	}
	return r2.PrfX(led, dig, unit, outPath)
}
