package nx

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// TipJournal is the cross-stage run tip for one offline evaluation.
// Pack, freeze-weight, and regret stages must agree before emission.
type TipJournal struct {
	Root string

	packArm int
	packFP  string
	wArm    int
	wFP     string
	rgArm   int
	rgFP    string
}

// NewTip builds an empty tip journal bound to root.
func NewTip(root string) *TipJournal {
	return &TipJournal{Root: root, packArm: -1, wArm: -1, rgArm: -1}
}

func (t *TipJournal) path() string {
	return filepath.Join(t.Root, "data", "run_tip.bin")
}

// Reset clears in-memory tips and removes on-disk residue from crashed runs.
func (t *TipJournal) Reset() {
	if t == nil {
		return
	}
	t.packArm, t.wArm, t.rgArm = -1, -1, -1
	t.packFP, t.wFP, t.rgFP = "", "", ""
	_ = os.Remove(t.path())
}

// PackFP hashes ordered cite tags.
func PackFP(rows []ZnRow) string {
	var b strings.Builder
	for _, r := range rows {
		b.WriteString(r.Tag)
		b.WriteByte(';')
	}
	sum := sha256.Sum256([]byte(b.String()))
	return hex.EncodeToString(sum[:8])
}

// WeightFP hashes freeze-epoch reconstructed weights.
func WeightFP(w Weights, freeze uint32) string {
	payload := fmt.Sprintf("fr=%d|b=%.10g", freeze, w.B)
	for _, v := range w.W {
		payload += fmt.Sprintf("|%.10g", v)
	}
	sum := sha256.Sum256([]byte(payload))
	return hex.EncodeToString(sum[:8])
}

// RegretFP hashes arm regret observations.
func RegretFP(unit RgUnit) string {
	payload := fmt.Sprintf("%s|%d|%d|%s", unit.Arm, unit.RegretMilli, unit.Seed, strings.Join(unit.Cites, ","))
	sum := sha256.Sum256([]byte(payload))
	return hex.EncodeToString(sum[:8])
}

// CommitPack records packing tip for armIx.
func (t *TipJournal) CommitPack(armIx int, rows []ZnRow) {
	if t == nil {
		return
	}
	t.packArm = armIx
	t.packFP = PackFP(rows)
	t.wArm, t.wFP = -1, ""
	t.rgArm, t.rgFP = -1, ""
	t.flush()
}

// CommitWeights records freeze-weight tip for armIx.
func (t *TipJournal) CommitWeights(armIx int, w Weights, freeze uint32) {
	if t == nil {
		return
	}
	t.wArm = armIx
	t.wFP = WeightFP(w, freeze)
	t.rgArm, t.rgFP = -1, ""
	t.flush()
}

// CommitRegret records regret tip for armIx.
func (t *TipJournal) CommitRegret(armIx int, unit RgUnit) {
	if t == nil {
		return
	}
	t.rgArm = armIx
	t.rgFP = RegretFP(unit)
	t.flush()
}

// Agreed reports whether pack, weight, and regret tips all match armIx.
func (t *TipJournal) Agreed(armIx int) bool {
	if t == nil {
		return false
	}
	return t.packArm == armIx && t.wArm == armIx && t.rgArm == armIx &&
		t.packFP != "" && t.wFP != "" && t.rgFP != ""
}

func (t *TipJournal) flush() {
	if t == nil || t.Root == "" {
		return
	}
	buf := make([]byte, 0, 64)
	buf = append(buf, []byte("TIP1")...)
	buf = binary.LittleEndian.AppendUint32(buf, uint32(int32(t.packArm)))
	buf = append(buf, pad16(t.packFP)...)
	buf = binary.LittleEndian.AppendUint32(buf, uint32(int32(t.wArm)))
	buf = append(buf, pad16(t.wFP)...)
	buf = binary.LittleEndian.AppendUint32(buf, uint32(int32(t.rgArm)))
	buf = append(buf, pad16(t.rgFP)...)
	_ = os.WriteFile(t.path(), buf, 0o644)
}

func pad16(s string) []byte {
	b := make([]byte, 16)
	copy(b, []byte(s))
	return b
}
