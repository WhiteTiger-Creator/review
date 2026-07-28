package w9

import (
	"crypto/sha256"
	"fmt"

	"bnmod/internal"
)

// JwPreview emits intermediate discontinuity counters for offline dumps.
func JwPreview(unit internal.LatticeUnit, arms []internal.JumpArm, partIx int) internal.JumpDigest {
	name := "none"
	var seed uint64
	rot := 0
	if partIx >= 0 && partIx < len(arms) {
		name = arms[partIx].Name
		seed = arms[partIx].Seed
		rot = arms[partIx].Rotate
	}
	payload := fmt.Sprintf("gauge|%s|%d|%d|%d|%d|%s", name, unit.Ka, unit.Kb, unit.Lim, rot, unit.Hex)
	sum := sha256.Sum256([]byte(payload))
	hex := fmt.Sprintf("%x", sum[:8])
	tag := ""
	if len(unit.WTags) > 0 {
		tag = unit.WTags[0]
	} else if len(unit.Tags) > 0 {
		tag = unit.Tags[0]
	}
	ukSum := sha256.Sum256([]byte("unit|" + unit.Hex + "|" + name))
	uk := fmt.Sprintf("%x", ukSum[:8])
	return internal.JumpDigest{
		Hex: hex, Arm: name, Seed: seed, Rotate: rot,
		Ka: unit.Ka, Kb: unit.Kb, Lim: unit.Lim, LatHex: unit.Hex,
		ScoreTag: tag, UnitKey: uk, Cite: tag,
	}
}
