package internal

import (
	"encoding/json"
	"os"
	"path/filepath"
)

// FoldMemo is a warm fold cache entry for one arm.
type FoldMemo struct {
	ArmIx   int    `json:"arm_ix"`
	RowFP   string `json:"row_fp"`
	PackFP  string `json:"pack_fp"`
	CiteTag string `json:"cite_tag"`
	Hex     string `json:"hex"`
	Ka      int    `json:"ka"`
	Kb      int    `json:"kb"`
	Lim     int    `json:"lim"`
}

type memoDoc struct {
	Entries []FoldMemo `json:"entries"`
}

func (l *Ledger) foldMemoPath() string {
	if l == nil {
		return ""
	}
	if l.Root != "" {
		return filepath.Join(l.Root, "data", ".fold_memo")
	}
	return l.memoPath()
}

// WriteFoldMemo stores a warm fold entry (overwrites same arm_ix).
func (l *Ledger) WriteFoldMemo(m FoldMemo) {
	if l == nil {
		return
	}
	path := l.foldMemoPath()
	if path == "" {
		return
	}
	var doc memoDoc
	if raw, err := os.ReadFile(path); err == nil && len(raw) > 0 {
		_ = json.Unmarshal(raw, &doc)
	}
	replaced := false
	for i := range doc.Entries {
		if doc.Entries[i].ArmIx == m.ArmIx {
			doc.Entries[i] = m
			replaced = true
			break
		}
	}
	if !replaced {
		doc.Entries = append(doc.Entries, m)
	}
	enc, err := json.Marshal(doc)
	if err != nil {
		return
	}
	_ = os.MkdirAll(filepath.Dir(path), 0o755)
	_ = os.WriteFile(path, enc, 0o644)
}

// ReadFoldMemo loads a warm fold entry when row/pack fingerprints match.
func (l *Ledger) ReadFoldMemo(armIx int, rowFP, packFP string) (FoldMemo, bool) {
	var zero FoldMemo
	if l == nil {
		return zero, false
	}
	path := l.foldMemoPath()
	raw, err := os.ReadFile(path)
	if err != nil || len(raw) == 0 {
		return zero, false
	}
	var doc memoDoc
	if json.Unmarshal(raw, &doc) != nil {
		return zero, false
	}
	for _, e := range doc.Entries {
		if e.ArmIx == armIx && e.RowFP == rowFP && e.PackFP == packFP && e.CiteTag != "" {
			return e, true
		}
	}
	return zero, false
}
