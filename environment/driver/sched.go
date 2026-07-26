package driver

import (
	"path/filepath"
	"strings"
)

func RunGridFull(out string) int {
	if err := EnsureAnchorStaging(); err != nil {
		return 1
	}
	tip, ov, fp, err := ResolvePolicy()
	if err != nil {
		return 1
	}
	var rows []GridRow
	for _, pf := range ProfileFiles() {
		row, err := RunFamily(pf, uint32(ov.Gen))
		if err != nil {
			return 1
		}
		rows = append(rows, row)
	}
	if err := WriteReport(out, rows); err != nil {
		return 1
	}
	auditPath := filepath.Join(filepath.Dir(out), "replay_audit.json")
	relPath := ov.Path
	if idx := strings.Index(relPath, "/pack/"); idx >= 0 {
		relPath = relPath[idx+1:]
	}
	audit := ReplayAudit{
		TipGen:            tip,
		PolicyGen:         ov.Gen,
		PolicyID:          ov.PolicyID,
		PolicyPath:        relPath,
		LedgerFingerprint: fp,
	}
	if err := WriteAudit(auditPath, audit); err != nil {
		return 1
	}
	return 0
}
