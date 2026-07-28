package w9

import (
	"bnmod/internal"
)

// JwW rebinds a lattice unit under discontinuity arms for a partition index.
func JwW(led *internal.Ledger, unit internal.LatticeUnit, arms []internal.JumpArm, partIx int) internal.JumpDigest {
	_ = led
	return JwPreview(unit, arms, partIx)
}

// JwX is the exported stage entry that calls JwW.
func JwX(led *internal.Ledger, unit internal.LatticeUnit, arms []internal.JumpArm, partIx int) internal.JumpDigest {
	return JwW(led, unit, arms, partIx)
}
