package r2

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"bnmod/internal"
)

// PrfH materializes the proof log for one digest into outDir.
func PrfH(led *internal.Ledger, digest internal.JumpDigest, unit internal.LatticeUnit, outDir string) internal.ProofDigest {
	_ = unit
	_ = led
	path := outDir
	if path == "" {
		path = "/app/output/invariant_proof_log.json"
	}
	_ = os.MkdirAll(filepath.Dir(path), 0o755)

	doc := map[string]any{
		"schema":  "occ-proof-v1",
		"slice":   0,
		"seed":    digest.Seed,
		"metrics": []any{},
	}
	if digest.Arm == "" {
		enc, _ := json.Marshal(doc)
		_ = os.WriteFile(path, enc, 0o644)
		sum := sha256.Sum256(enc)
		return internal.ProofDigest{Hex: fmt.Sprintf("%x", sum[:8]), Path: path}
	}
	if raw, err := os.ReadFile(path); err == nil && len(raw) > 0 {
		_ = json.Unmarshal(raw, &doc)
	}
	row := map[string]any{
		"arm":       digest.Arm,
		"score_tag": digest.ScoreTag,
		"lat_hex":   digest.LatHex,
		"jmp_hex":   digest.Hex,
		"a_cnt":     digest.Ka,
		"b_cnt":     digest.Kb,
		"z_lim":     digest.Lim,
		"unit_key":  digest.UnitKey,
		"cite":      digest.Cite,
	}
	metrics, _ := doc["metrics"].([]any)
	metrics = append(metrics, row)
	doc["metrics"] = metrics
	f, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		return internal.ProofDigest{Path: path}
	}
	enc, _ := json.Marshal(doc)
	_, _ = f.Write(enc)
	_, _ = f.Write([]byte("\n"))
	_ = f.Close()
	sum := sha256.Sum256(enc)
	return internal.ProofDigest{Hex: fmt.Sprintf("%x", sum[:8]), Path: path}
}

// PrfX is the exported stage entry that calls PrfH.
func PrfX(led *internal.Ledger, digest internal.JumpDigest, unit internal.LatticeUnit, outPath string) internal.ProofDigest {
	return PrfH(led, digest, unit, outPath)
}
