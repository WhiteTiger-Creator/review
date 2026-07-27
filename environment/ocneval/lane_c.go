package ocneval

import (
	"bnmod/internal"
	"bnmod/pipe/p34"
	"bnmod/w9"
)

func init() {
	p34.AfterBind = ApplyC
}

// ApplyC is the post-bind pipe adapter.
func ApplyC(led *internal.Ledger, dig internal.JumpDigest, unit internal.LatticeUnit, arms []internal.JumpArm, partIx int) internal.JumpDigest {
	_ = led
	if dig.Arm == "" {
		return dig
	}
	return w9.Gauge(unit, arms, partIx)
}
