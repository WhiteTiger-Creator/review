package k7w

import (
	"encoding/binary"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"sort"

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

type RetryStep struct {
	Frame        string `json:"frame"`
	Epoch        int    `json:"epoch"`
	TransitionID string `json:"transition_id"`
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
	wa, _ := LoadWitness(filepath.Join(envRoot, "data/wt_pair/a.json"))
	wb, _ := LoadWitness(filepath.Join(envRoot, "data/wt_pair/b.json"))
	wc, _ := LoadWitness(filepath.Join(envRoot, "data/wt_pair/c.json"))
	witness := append(append(wa, wb...), wc...)

	var lines []model.ReportLine
	var names []string
	for n := range pack.Entries {
		names = append(names, n)
	}
	sort.Strings(names)
	idx := 0
	for _, name := range names {
		frame := pack.Entries[name]
		ps, err := pipeline.ResolvePackRow(frame, tmpl.Primary)
		if err != nil {
			return err
		}
		mid, _ := pipeline.StampMemoID(ps.Stamp)
		var anchor int64
		if idx < len(witness) {
			anchor = pipeline.TimingAnchor(witness[idx].DSInception, witness[idx].CertNotBefore)
		}
		tid := "t-" + name
		ok, _ := pipeline.RecordPack(mid, tid, ps.Scope)
		if !ok {
			idx++
			continue
		}
		lines = append(lines, emit.Line("L-"+name, ps.Scope, tid, emit.RationaleFor(ps.Scope)+" stamp="+ps.Stamp, anchor))
		idx++
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
