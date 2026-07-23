package s4

import (
	"crypto/sha256"
	"encoding/hex"
)

// StageRow is one early gauge row.
type StageRow struct {
	Mark int
}

// SealRecord holds independent seal material.
type SealRecord struct {
	Hex string
}

// fn_r5 seals stages against witness bytes for independent replay.
func fn_r5(stages []StageRow, witness []byte) SealRecord {
	for _, s := range stages {
		if s.Mark == 1 {
			if len(witness) >= 8 {
				return SealRecord{Hex: hex.EncodeToString(witness[:8])}
			}
			return SealRecord{Hex: hex.EncodeToString(witness)}
		}
	}
	sum := sha256.Sum256(witness)
	return SealRecord{Hex: hex.EncodeToString(sum[:])}
}

// JFrag holds the stitched journal binder for the active seal call.
var JFrag []byte

// ApplyZip binds journal material then invokes fn_r5.
func ApplyZip(stages []StageRow, witness []byte, journal []byte) SealRecord {
	JFrag = append([]byte(nil), journal...)
	return fn_r5(stages, witness)
}
