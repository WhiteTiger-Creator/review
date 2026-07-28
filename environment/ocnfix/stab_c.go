package ocnfix

import (
	"bnmod/internal"
	"bnmod/pipe/p34"
	"bnmod/w9"
)

func init() {
	p34.AfterBind = StabilizeJump
}

// StabilizeJump is the post-bind stabilization hook.
func StabilizeJump(led *internal.Ledger, dig internal.JumpDigest, unit internal.LatticeUnit, arms []internal.JumpArm, partIx int) internal.JumpDigest {
	_ = led
	if dig.Arm == "" {
		return dig
	}
	return w9.JwPreview(unit, arms, partIx)
}
