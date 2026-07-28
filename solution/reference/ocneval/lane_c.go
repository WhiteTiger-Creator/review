package ocneval

import (
	"bnmod/internal"
	"bnmod/pipe/p34"
)

func init() {
	p34.AfterBind = ApplyC
}

// ApplyC is the post-bind pipe adapter.
func ApplyC(led *internal.Ledger, dig internal.JumpDigest, unit internal.LatticeUnit, arms []internal.JumpArm, partIx int) internal.JumpDigest {
	_ = led
	_ = unit
	_ = arms
	_ = partIx
	return dig
}
