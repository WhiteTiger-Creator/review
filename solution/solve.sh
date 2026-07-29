#!/bin/bash
set -euo pipefail
cd /app/environment

cat > ingest.go <<'EOF'
package k7w

import (
	"encoding/binary"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"k7w/internal/emit"
	"k7w/internal/model"
	"k7w/internal/wire"
	"k7w/pipeline"
)

type Pack struct {
	Entries map[string][]byte
}

func LoadPack(path string) (*Pack, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	if len(data) < 8 || string(data[:4]) != "K7PK" {
		return nil, errors.New("bad pack")
	}
	count := int(binary.BigEndian.Uint32(data[4:8]))
	pos := 8
	out := make(map[string][]byte)
	for i := 0; i < count; i++ {
		if pos+4 > len(data) {
			return nil, errors.New("trunc pack")
		}
		nl := int(binary.BigEndian.Uint32(data[pos : pos+4]))
		pos += 4
		if pos+nl+4 > len(data) {
			return nil, errors.New("trunc name")
		}
		name := string(data[pos : pos+nl])
		pos += nl
		bl := int(binary.BigEndian.Uint32(data[pos : pos+4]))
		pos += 4
		if pos+bl > len(data) {
			return nil, errors.New("trunc blob")
		}
		out[name] = append([]byte(nil), data[pos:pos+bl]...)
		pos += bl
	}
	return &Pack{Entries: out}, nil
}

type Witness struct {
	CertNotBefore int64  `json:"cert_not_before"`
	DSInception   int64  `json:"ds_inception"`
	ScopeExpect   string `json:"scope_expect"`
}

func LoadWitness(path string) ([]Witness, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var rows []Witness
	if err := json.Unmarshal(raw, &rows); err != nil {
		return nil, err
	}
	return rows, nil
}

func LoadWitnessRows(dir string) (map[string]Witness, error) {
	paths, err := filepath.Glob(filepath.Join(dir, "*.json"))
	if err != nil {
		return nil, err
	}
	sort.Strings(paths)
	out := make(map[string]Witness)
	for _, path := range paths {
		got, err := LoadWitness(path)
		if err != nil || len(got) == 0 {
			return nil, err
		}
		key := sidecarCaptureKey(path)
		if key == "" {
			return nil, errors.New("bad sidecar name")
		}
		out[key] = got[0]
	}
	return out, nil
}

func sidecarCaptureKey(path string) string {
	stem := strings.TrimSuffix(filepath.Base(path), ".json")
	if i := strings.Index(stem, "-"); i > 0 {
		prefix := stem[:i]
		allDigits := true
		for _, c := range prefix {
			if c < '0' || c > '9' {
				allDigits = false
				break
			}
		}
		if allDigits {
			return stem[i+1:]
		}
	}
	return stem
}

func witnessForCapture(witness map[string]Witness, capture string, idx int, legacy []Witness) Witness {
	if w, ok := witness[capture]; ok {
		return w
	}
	if idx < len(legacy) {
		return legacy[idx]
	}
	return Witness{}
}

type RetryStep struct {
	Frame        string `json:"frame"`
	Epoch        int    `json:"epoch"`
	TransitionID string `json:"transition_id"`
}

func lessCaptureName(a, b string) bool {
	if strings.HasPrefix(a, b+"-") {
		return true
	}
	if strings.HasPrefix(b, a+"-") {
		return false
	}
	return a < b
}

func CheckBundle(envRoot string) error {
	pack, err := LoadPack(filepath.Join(envRoot, "bundle/k7/base.k7"))
	if err != nil {
		return err
	}
	for _, blob := range pack.Entries {
		if _, err := wire.CanonStamp(blob); err != nil {
			return err
		}
	}
	return nil
}

func RunEmit(envRoot, outPath string) error {
	pipeline.ResetMemo()
	pack, err := LoadPack(filepath.Join(envRoot, "bundle/k7/base.k7"))
	if err != nil {
		return err
	}
	tmplRaw, err := os.ReadFile(filepath.Join(envRoot, "data/tmpl_set.json"))
	if err != nil {
		return err
	}
	var tmpl struct {
		Primary model.Tmpl `json:"primary"`
	}
	if err := json.Unmarshal(tmplRaw, &tmpl); err != nil {
		return err
	}
	witnessMap, err := LoadWitnessRows(filepath.Join(envRoot, "data/wt_pair"))
	if err != nil {
		return err
	}
	var legacy []Witness
	for _, stem := range []string{"a", "b", "c"} {
		if rows, err := LoadWitness(filepath.Join(envRoot, "data/wt_pair", stem+".json")); err == nil && len(rows) > 0 {
			legacy = append(legacy, rows[0])
		}
	}

	var lines []model.ReportLine
	var names []string
	for n := range pack.Entries {
		names = append(names, n)
	}
	sort.Slice(names, func(i, j int) bool {
		return lessCaptureName(names[i], names[j])
	})
	for idx, name := range names {
		frame := pack.Entries[name]
		ps, err := pipeline.ResolvePackRow(frame, tmpl.Primary)
		if err != nil {
			return err
		}
		mid, _ := pipeline.StampMemoID(ps.Stamp)
		w := witnessForCapture(witnessMap, name, idx, legacy)
		anchor := pipeline.TimingAnchor(w.DSInception, w.CertNotBefore)
		tid := "t-" + name
		ok, _ := pipeline.RecordPack(mid, tid, ps.Scope)
		if !ok {
			continue
		}
		lines = append(lines, emit.Line("L-"+name, ps.Scope, tid, emit.RationaleFor(ps.Scope)+" stamp="+ps.Stamp, anchor))
	}

	retryRaw, _ := os.ReadFile(filepath.Join(envRoot, "data/retry_schedules.json"))
	var sched struct {
		Steps []RetryStep `json:"steps"`
	}
	_ = json.Unmarshal(retryRaw, &sched)
	for _, step := range sched.Steps {
		frame := pack.Entries[step.Frame]
		ok, err := pipeline.RecordRetry(frame, step.Epoch, step.TransitionID)
		if err != nil || !ok {
			continue
		}
		lines = append(lines, emit.Line("R-"+step.TransitionID, "retry", step.TransitionID, "retry delivery", 0))
	}

	doc := model.ReportDoc{
		Lines:      lines,
		MetricFold: pipeline.MetricFold(lines, len(pack.Entries)),
	}
	raw, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(outPath, raw, 0o644)
}
EOF

cat > slice/chop.go <<'EOF'
package slice

import (
	"k7w/internal/model"
	"k7w/internal/wire"
)

func ChopSegment(buf []byte, out *model.Chunk) (int, error) {
	body, err := wire.BodyOf(buf)
	if err != nil {
		return 0, err
	}
	can := wire.CanonicalTLV(body)
	chunks, err := wire.ParseChunks(can)
	if err != nil {
		return 0, err
	}
	if len(chunks) == 0 {
		return len(buf), nil
	}
	*out = chunks[0]
	return len(buf), nil
}

func CanonDigest(frame []byte) (string, error) {
	return wire.CanonStamp(frame)
}
EOF

cat > slot/choose.go <<'EOF'
package slot

import (
	"errors"
	"k7w/internal/model"
)

func ChooseAlt(chunks []model.Chunk, prof model.Tmpl) (model.AltPick, error) {
	_ = prof
	for i := len(chunks) - 1; i >= 0; i-- {
		c := chunks[i]
		if c.Tag == model.TagAltDNS || c.Tag == model.TagAltSSH {
			return model.AltPick{Kind: c.Tag, Value: string(c.Value)}, nil
		}
	}
	return model.AltPick{}, errors.New("no alt")
}
EOF

cat > memo/mark.go <<'EOF'
package memo

import (
	"crypto/sha256"
	"encoding/hex"
	"k7w/internal/model"
)

var seen = map[string]struct{}{}

func MarkUnique(id model.MemoID, row model.Transition) (bool, error) {
	if row.ID == "" {
		return false, nil
	}
	material := []byte(row.ID)
	if row.Code != "retry" {
		material = append(material, id[:]...)
	}
	h := sha256.Sum256(material)
	key := hex.EncodeToString(h[:])
	if _, ok := seen[key]; ok {
		return false, nil
	}
	seen[key] = struct{}{}
	return true, nil
}

func ResetLedger() {
	seen = map[string]struct{}{}
}
EOF

cat > range/narrow.go <<'EOF'
package narrow

import (
	"k7w/internal/model"
)

func NarrowSpan(ds model.SpanLo, cert model.SpanHi) (model.Anchor, error) {
	a := ds.Inception
	b := cert.NotBefore
	if b < a {
		a = b
	}
	if a < 0 {
		a = 0
	}
	return model.Anchor{Unix: a}, nil
}
EOF

cat > pipeline/fold.go <<'EOF'
package pipeline

import (
	"fmt"
	"regexp"
	"sort"
	"strings"

	"k7w/internal/model"
)

var stampRe = regexp.MustCompile(`stamp=([0-9a-f]{64})`)

func MetricFold(lines []model.ReportLine, packCount int) string {
	var lrows, rrows []model.ReportLine
	for _, ln := range lines {
		if strings.HasPrefix(ln.LineID, "L-") {
			lrows = append(lrows, ln)
		} else if strings.HasPrefix(ln.LineID, "R-") {
			rrows = append(rrows, ln)
		}
	}
	sort.Slice(lrows, func(i, j int) bool { return lrows[i].LineID < lrows[j].LineID })
	sort.Slice(rrows, func(i, j int) bool { return rrows[i].LineID < rrows[j].LineID })
	var parts []string
	for _, ln := range lrows {
		m := stampRe.FindStringSubmatch(ln.RationaleText)
		stamp := ""
		if len(m) > 1 {
			stamp = m[1]
		}
		parts = append(parts, fmt.Sprintf("%s|%s|%d|%s", ln.LineID, ln.ScopeCode, ln.TimingAnchor, stamp))
	}
	for _, ln := range rrows {
		parts = append(parts, fmt.Sprintf("%s|%s", ln.LineID, ln.TransitionID))
	}
	parts = append(parts, fmt.Sprintf("pack:%d", packCount))
	return fold64(strings.Join(parts, "\n"))
}

func fold64(payload string) string {
	var total uint64
	mask := ^uint64(0)
	for i := 0; i < len(payload); i++ {
		total = (total + uint64(i+1)*uint64(payload[i])) & mask
	}
	return fmt.Sprintf("%08x", uint32(total))
}
EOF

make build
mkdir -p /app/output
./bin/w7 emit --out /app/output/k7_witness_report.json
