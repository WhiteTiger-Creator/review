package internal

import (
	"encoding/binary"
	"math"
	"os"
	"path/filepath"
)

// WriteRowCache persists scored rows for later re-dot checks (ROW1).
func WriteRowCache(root string, rows []RowTag) {
	if root == "" || len(rows) == 0 {
		return
	}
	buf := make([]byte, 0, 4+2+len(rows)*24)
	buf = append(buf, []byte("ROW1")...)
	buf = binary.LittleEndian.AppendUint16(buf, uint16(len(rows)))
	for _, r := range rows {
		buf = binary.LittleEndian.AppendUint16(buf, r.Ix)
		buf = append(buf, r.Role, 0)
		u := math.Float64bits(r.Score)
		buf = binary.LittleEndian.AppendUint64(buf, u)
	}
	_ = os.MkdirAll(filepath.Join(root, "data"), 0o755)
	_ = os.WriteFile(filepath.Join(root, "data", rowCacheName), buf, 0o644)
}

// LoadRowCache loads ROW1 scored rows when present.
func LoadRowCache(root string) ([]RowTag, bool) {
	raw, err := os.ReadFile(filepath.Join(root, "data", rowCacheName))
	if err != nil || len(raw) < 6 || string(raw[:4]) != "ROW1" {
		return nil, false
	}
	n := int(binary.LittleEndian.Uint16(raw[4:6]))
	off := 6
	out := make([]RowTag, 0, n)
	for i := 0; i < n; i++ {
		if off+12 > len(raw) {
			return nil, false
		}
		ix := binary.LittleEndian.Uint16(raw[off:])
		role := raw[off+2]
		off += 4
		u := binary.LittleEndian.Uint64(raw[off:])
		off += 8
		out = append(out, RowTag{Ix: ix, Role: role, Score: math.Float64frombits(u)})
	}
	return out, true
}

// RedotOK reports whether scored rows still match frozen weights under pin order.
func RedotOK(root string, rows []RowTag) bool {
	wraw, err := ReadFile(root + "/weights/w_blob.bin")
	if err != nil {
		return false
	}
	w, err := ParseWts(wraw)
	if err != nil || len(w.W) == 0 {
		return false
	}
	fraw, err := ReadFile(root + "/fixtures/feat_blob.bin")
	if err != nil {
		return false
	}
	recs, err := ParseFeat(fraw)
	if err != nil {
		return false
	}
	by := map[uint16]Rec{}
	for _, r := range recs {
		by[r.Id] = r
	}
	for _, row := range rows {
		rec, ok := by[row.Ix]
		if !ok {
			return false
		}
		sc := DotBias(w.W, rec.Feats, w.Bias)
		if math.Abs(sc-row.Score) > 1e-9 {
			return false
		}
	}
	return true
}
