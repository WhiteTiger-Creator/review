package p34

import "bnmod/internal"

// AfterBind is an optional post-bind adapter installed by the evaluation driver.
var AfterBind func(led *internal.Ledger, dig internal.JumpDigest, unit internal.LatticeUnit, arms []internal.JumpArm, partIx int) internal.JumpDigest
