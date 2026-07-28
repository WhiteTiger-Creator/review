package w9

import (
	"crypto/sha256"
	"fmt"

	"bnmod/internal"
)

// JwW rebinds a lattice unit under discontinuity arms for a partition index.
func JwW(led *internal.Ledger, unit internal.LatticeUnit, arms []internal.JumpArm, partIx int) internal.JumpDigest {
	if partIx < 0 || partIx >= len(arms) {
		return internal.JumpDigest{}
	}
	if led == nil || !led.ExpectLat(partIx, unit) || unit.Hex == "" || unit.CiteTag == "" || unit.Seal == "" || unit.Seal != internal.AuthSeal(unit.CiteTag) || unit.PackFP == "" || unit.PackFP != led.TipPackFP() {
		return internal.JumpDigest{}
	}
	arm := arms[partIx]
	if arm.Name == "" {
		return internal.JumpDigest{}
	}
	ka, kb, lim := unit.Ka, unit.Kb, unit.Lim
	if lim < 0 {
		lim = 0
	}
	if lim > 0 {
		jump := arm.Jump
		if jump < 0 {
			jump = -jump
		}
		ka = (unit.Ka + jump) % lim
		if ka < 0 {
			ka += lim
		}
		kb = lim - ka
	} else {
		ka = 0
		kb = 0
	}
	tag := unit.CiteTag
	ukPayload := fmt.Sprintf("unit|%s|%s", unit.Hex, arm.Name)
	ukSum := sha256.Sum256([]byte(ukPayload))
	uk := fmt.Sprintf("%x", ukSum[:8])
	payload := fmt.Sprintf("jmp|%s|%d|%d|%d|%d|%s|%d", arm.Name, arm.Seed, ka, kb, lim, unit.Hex, arm.Rotate)
	sum := sha256.Sum256([]byte(payload))
	hex := fmt.Sprintf("%x", sum[:8])
	dig := internal.JumpDigest{
		Hex: hex, Arm: arm.Name, Seed: arm.Seed, Rotate: arm.Rotate,
		Ka: ka, Kb: kb, Lim: lim, LatHex: unit.Hex,
		ScoreTag: tag, UnitKey: uk, Cite: tag,
	}
	led.CommitJmp(partIx, dig)
	return dig
}

// JwX is the exported stage entry that calls JwW.
func JwX(led *internal.Ledger, unit internal.LatticeUnit, arms []internal.JumpArm, partIx int) internal.JumpDigest {
	return JwW(led, unit, arms, partIx)
}
