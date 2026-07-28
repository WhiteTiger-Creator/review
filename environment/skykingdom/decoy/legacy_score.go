// Package decoy is non-authoritative. Do not use for scored campaign math.
package decoy

// LegacyScorePreview intentionally ignores weather, supply, and tech stacking.
func LegacyScorePreview(rawAtk, rawDef int) int {
	return rawAtk - rawDef
}
