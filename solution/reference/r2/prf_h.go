package r2

import (
	"bnmod/internal"
)

// PrfH materializes the proof log for one digest into outDir.
func PrfH(led *internal.Ledger, digest internal.JumpDigest, unit internal.LatticeUnit, outDir string) internal.ProofDigest {
	path := outDir
	if path == "" {
		path = "/app/output/invariant_proof_log.json"
	}
	if digest.Arm == "" {
		return internal.ProofDigest{Path: path}
	}
	if led == nil {
		return internal.ProofDigest{Path: path}
	}
	if unit.CiteTag != "" && digest.Cite != unit.CiteTag {
		return internal.ProofDigest{Path: path}
	}
	if !led.MatchJmp(digest) {
		return internal.ProofDigest{Path: path}
	}
	led.Upsert(digest)
	pd, err := led.Flush(path)
	if err != nil {
		return internal.ProofDigest{Path: path}
	}
	return pd
}

// PrfX is the exported stage entry that calls PrfH.
func PrfX(led *internal.Ledger, digest internal.JumpDigest, unit internal.LatticeUnit, outPath string) internal.ProofDigest {
	return PrfH(led, digest, unit, outPath)
}
