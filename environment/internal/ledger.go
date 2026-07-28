package internal

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
)

// Ledger is the cross-stage tip journal for one offline evaluation run.
type Ledger struct {
	Root string
	Out  string

	packArm int
	packFP  string
	rowArm  int
	rowFP   string
	latArm  int
	latFP   string
	jmpArm  int
	jmpFP   string

	seed    uint64
	seedSet bool
	rows    []metricRow
	gen     int
}

type metricRow struct {
	Arm      string `json:"arm"`
	ScoreTag string `json:"score_tag"`
	LatHex   string `json:"lat_hex"`
	JmpHex   string `json:"jmp_hex"`
	ACnt     int    `json:"a_cnt"`
	BCnt     int    `json:"b_cnt"`
	ZLim     int    `json:"z_lim"`
	UnitKey  string `json:"unit_key"`
	Cite     string `json:"cite"`
}

type tipDoc struct {
	Schema  string      `json:"schema"`
	Slice   int         `json:"slice"`
	Seed    uint64      `json:"seed"`
	Metrics []metricRow `json:"metrics"`
}

type tipSnap struct {
	Gen     int    `json:"gen"`
	PackArm int    `json:"pack_arm"`
	PackFP  string `json:"pack_fp"`
	RowArm  int    `json:"row_arm"`
	RowFP   string `json:"row_fp"`
	LatArm  int    `json:"lat_arm"`
	LatFP   string `json:"lat_fp"`
	JmpArm  int    `json:"jmp_arm"`
	JmpFP   string `json:"jmp_fp"`
}

// NewLedger builds an empty run journal bound to root and out path.
func NewLedger(root, out string) *Ledger {
	return &Ledger{Root: root, Out: out, packArm: -1, rowArm: -1, latArm: -1, jmpArm: -1}
}

// Reset clears tip state and on-disk residue for a fresh run.
func (l *Ledger) Reset() {
	if l == nil {
		return
	}
	l.packArm, l.rowArm, l.latArm, l.jmpArm = -1, -1, -1, -1
	l.packFP, l.rowFP, l.latFP, l.jmpFP = "", "", "", ""
	l.seed, l.seedSet = 0, false
	l.rows = nil
	l.gen = 0
	if l.Out != "" {
		_ = os.Remove(l.Out)
		_ = os.Remove(l.Out + ".tmp")
		_ = os.Remove(l.tipPath())
		_ = os.Remove(l.memoPath())
	}
	if l.Root != "" {
		_ = os.Remove(filepath.Join(l.Root, "data", ".fold_memo"))
		_ = os.Remove(filepath.Join(l.Root, "data", ".tip_snap"))
	}
}

func (l *Ledger) tipPath() string {
	if l == nil || l.Out == "" {
		return ""
	}
	return l.Out + ".tip"
}

func (l *Ledger) memoPath() string {
	if l == nil || l.Out == "" {
		return ""
	}
	return l.Out + ".memo"
}

func (l *Ledger) snapPath() string {
	if l == nil {
		return ""
	}
	if l.Root != "" {
		return filepath.Join(l.Root, "data", ".tip_snap")
	}
	if l.Out != "" {
		return l.Out + ".snap"
	}
	return ""
}


func (l *Ledger) reloadTips() {
	if l == nil {
		return
	}
	path := l.snapPath()
	raw, err := os.ReadFile(path)
	if err != nil || len(raw) == 0 {
		l.packArm, l.rowArm, l.latArm, l.jmpArm = -1, -1, -1, -1
		l.packFP, l.rowFP, l.latFP, l.jmpFP = "", "", "", ""
		l.gen = 0
		return
	}
	var s tipSnap
	if json.Unmarshal(raw, &s) != nil {
		return
	}
	l.gen = s.Gen
	l.packArm, l.packFP = s.PackArm, s.PackFP
	l.rowArm, l.rowFP = s.RowArm, s.RowFP
	l.latArm, l.latFP = s.LatArm, s.LatFP
	l.jmpArm, l.jmpFP = s.JmpArm, s.JmpFP
}

// PackFP hashes concatenated feat|pin|wts bytes.
func PackFP(feat, pin, wts []byte) string {
	sum := sha256.Sum256(append(append(feat, pin...), wts...))
	return fmt.Sprintf("%x", sum[:8])
}

// RowsFP hashes ordered row tags (order-sensitive).
func RowsFP(rows []RowTag) string {
	payload := make([]byte, 0, 64*len(rows))
	for _, r := range rows {
		payload = append(payload, r.Tag...)
		payload = append(payload, '|')
		payload = append(payload, fmt.Sprintf("%d:%d", r.Ix, r.Role)...)
		payload = append(payload, ';')
	}
	sum := sha256.Sum256(payload)
	return fmt.Sprintf("%x", sum[:8])
}

// LatFP hashes lattice identity including cite, pack tip, and seal.
func LatFP(unit LatticeUnit) string {
	payload := fmt.Sprintf("%s|%s|%s|%s|%d|%d|%d|%d", unit.Hex, unit.CiteTag, unit.PackFP, unit.Seal, unit.Ka, unit.Kb, unit.Lim, len(unit.WTags))
	sum := sha256.Sum256([]byte(payload))
	return fmt.Sprintf("%x", sum[:8])
}

// JmpFP hashes jump digest identity material.
func JmpFP(d JumpDigest) string {
	payload := fmt.Sprintf("%s|%s|%d|%d|%d|%s", d.Arm, d.Hex, d.Ka, d.Kb, d.Lim, d.LatHex)
	sum := sha256.Sum256([]byte(payload))
	return fmt.Sprintf("%x", sum[:8])
}

// TipPackFP returns the durable pack tip fingerprint.
func (l *Ledger) TipPackFP() string {
	if l == nil {
		return ""
	}
	l.reloadTips()
	return l.packFP
}

// CommitPack records the pack tip for armIx and invalidates downstream tips.
func (l *Ledger) CommitPack(armIx int, fp string) {
	if l == nil {
		return
	}
	l.packArm = armIx
	l.packFP = fp
	l.rowArm, l.rowFP = -1, ""
	l.latArm, l.latFP = -1, ""
	l.jmpArm, l.jmpFP = -1, ""
	l.gen++
	l.PersistTips()
}

// ExpectPack reports whether the durable pack tip matches armIx and fp.
func (l *Ledger) ExpectPack(armIx int, fp string) bool {
	if l == nil {
		return false
	}
	l.reloadTips()
	return l.packArm == armIx && l.packFP != "" && l.packFP == fp
}

// CommitRows records the scored tip for armIx.
func (l *Ledger) CommitRows(armIx int, rows []RowTag) {
	if l == nil {
		return
	}
	l.rowArm = armIx
	l.rowFP = RowsFP(rows)
	l.latArm, l.latFP = -1, ""
	l.jmpArm, l.jmpFP = -1, ""
	l.gen++
	l.PersistTips()
}

// ExpectRows reports whether the durable row tip matches armIx and rows.
func (l *Ledger) ExpectRows(armIx int, rows []RowTag) bool {
	if l == nil {
		return false
	}
	l.reloadTips()
	return l.rowArm == armIx && l.rowFP != "" && l.rowFP == RowsFP(rows)
}

// CommitLat records the folded tip for armIx.
func (l *Ledger) CommitLat(armIx int, unit LatticeUnit) {
	if l == nil {
		return
	}
	l.latArm = armIx
	l.latFP = LatFP(unit)
	l.jmpArm, l.jmpFP = -1, ""
	l.gen++
	l.PersistTips()
}

// ExpectLat reports whether the durable lattice tip matches armIx and unit.
func (l *Ledger) ExpectLat(armIx int, unit LatticeUnit) bool {
	if l == nil {
		return false
	}
	l.reloadTips()
	return l.latArm == armIx && l.latFP != "" && l.latFP == LatFP(unit)
}

// CommitJmp records the rebound tip for armIx.
func (l *Ledger) CommitJmp(armIx int, d JumpDigest) {
	if l == nil {
		return
	}
	l.jmpArm = armIx
	l.jmpFP = JmpFP(d)
	l.gen++
	l.PersistTips()
}

// ExpectJmp reports whether the durable jump tip matches armIx and digest.
func (l *Ledger) ExpectJmp(armIx int, d JumpDigest) bool {
	if l == nil {
		return false
	}
	l.reloadTips()
	return l.jmpArm == armIx && l.jmpFP != "" && l.jmpFP == JmpFP(d)
}

// TipJmpArm returns the arm index of the current jump tip, or -1.
func (l *Ledger) TipJmpArm() int {
	if l == nil {
		return -1
	}
	l.reloadTips()
	return l.jmpArm
}

// MatchJmp reports whether digest matches the durable jump tip.
func (l *Ledger) MatchJmp(d JumpDigest) bool {
	if l == nil {
		return false
	}
	l.reloadTips()
	return l.jmpArm >= 0 && l.jmpFP != "" && l.jmpFP == JmpFP(d)
}

// PinOrderOK reports whether row Ix sequence matches pinned order.
func PinOrderOK(root string, rows []RowTag) bool {
	raw, err := ReadFile(root + "/data/pin_s.lock")
	if err != nil {
		return false
	}
	pin, err := ParsePin(raw)
	if err != nil || pin.Slice != 3 || len(pin.Order) == 0 {
		return false
	}
	if len(rows) == 0 {
		return false
	}
	seen := make(map[uint16]struct{}, len(pin.Order))
	want := make([]uint16, 0, len(pin.Order))
	for _, id := range pin.Order {
		if _, ok := seen[id]; ok {
			continue
		}
		seen[id] = struct{}{}
		want = append(want, id)
	}
	if len(want) != len(rows) {
		return false
	}
	for i := range want {
		if rows[i].Ix != want[i] {
			return false
		}
	}
	return true
}

// Upsert merges one digest into the in-memory metrics journal.
func (l *Ledger) Upsert(d JumpDigest) {
	if l == nil || d.Arm == "" {
		return
	}
	if !l.seedSet {
		l.seed = d.Seed
		l.seedSet = true
	}
	cite := d.Cite
	if cite == "" {
		cite = d.ScoreTag
	}
	row := metricRow{
		Arm: d.Arm, ScoreTag: d.ScoreTag, LatHex: d.LatHex,
		JmpHex: d.Hex, ACnt: d.Ka, BCnt: d.Kb, ZLim: d.Lim,
		UnitKey: d.UnitKey, Cite: cite,
	}
	for i := range l.rows {
		if l.rows[i].Arm == row.Arm {
			l.rows[i] = row
			return
		}
	}
	l.rows = append(l.rows, row)
}

// Flush writes the sorted proof document atomically and clears durable tips.
func (l *Ledger) Flush(path string) (ProofDigest, error) {
	if l == nil {
		return ProofDigest{}, fmt.Errorf("nil ledger")
	}
	if path == "" {
		path = l.Out
	}
	if path == "" {
		path = "/app/output/invariant_proof_log.json"
	}
	_ = os.MkdirAll(filepath.Dir(path), 0o755)
	sort.SliceStable(l.rows, func(i, j int) bool {
		if l.rows[i].Arm == l.rows[j].Arm {
			return l.rows[i].Cite < l.rows[j].Cite
		}
		return l.rows[i].Arm < l.rows[j].Arm
	})
	doc := tipDoc{
		Schema:  "occ-proof-v1",
		Slice:   3,
		Seed:    l.seed,
		Metrics: append([]metricRow(nil), l.rows...),
	}
	enc, err := json.Marshal(doc)
	if err != nil {
		return ProofDigest{Path: path}, err
	}
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, enc, 0o644); err != nil {
		return ProofDigest{Path: path}, err
	}
	if err := os.Rename(tmp, path); err != nil {
		_ = os.WriteFile(path, enc, 0o644)
	}
	_ = os.WriteFile(l.tipPath(), []byte(fmt.Sprintf("gen=%d\n", len(l.rows))), 0o644)
	l.packArm, l.rowArm, l.latArm, l.jmpArm = -1, -1, -1, -1
	l.packFP, l.rowFP, l.latFP, l.jmpFP = "", "", "", ""
	l.gen++
	l.PersistTips()
	sum := sha256.Sum256(enc)
	return ProofDigest{Hex: fmt.Sprintf("%x", sum[:8]), Path: path}, nil
}
