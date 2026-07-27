package internal

import (
	"encoding/json"
	"os"
	"path/filepath"
)

// PersistTips persists tip state for the active evaluation run.
func (l *Ledger) PersistTips() {
	if l == nil {
		return
	}
	path := l.snapPath()
	if path == "" {
		return
	}
	s := tipSnap{
		Gen:     l.gen,
		PackArm: l.packArm, PackFP: l.packFP,
		RowArm: l.rowArm, RowFP: l.rowFP,
		LatArm: l.latArm, LatFP: l.latFP,
		JmpArm: l.jmpArm, JmpFP: l.jmpFP,
	}
	enc, err := json.Marshal(s)
	if err != nil {
		return
	}
	_ = os.MkdirAll(filepath.Dir(path), 0o755)
	_ = os.WriteFile(path, enc, 0o644)
}
