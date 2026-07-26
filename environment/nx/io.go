package nx

import (
	"encoding/binary"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"strings"
)

// ZoneRec is a raw zone record from a fixture pack.
type ZoneRec struct {
	Zone  uint16
	Lab   int16
	Feats []float64
	File  string
	Stamp uint32
}

// LoadZones reads every *.bin under fixtures/zones.
func LoadZones(root string) ([]ZoneRec, error) {
	dir := filepath.Join(root, "fixtures", "zones")
	ents, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	var out []ZoneRec
	for _, e := range ents {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".bin") {
			continue
		}
		path := filepath.Join(dir, e.Name())
		raw, err := os.ReadFile(path)
		if err != nil {
			return nil, err
		}
		recs, err := parseZone(raw, e.Name())
		if err != nil {
			return nil, err
		}
		out = append(out, recs...)
	}
	return out, nil
}

// MaxPackStamp returns the maximum zone-pack stamp under fixtures/zones.
func MaxPackStamp(root string) (uint32, error) {
	zs, err := LoadZones(root)
	if err != nil {
		return 0, err
	}
	var max uint32
	for _, z := range zs {
		if z.Stamp > max {
			max = z.Stamp
		}
	}
	return max, nil
}

func parseZone(raw []byte, file string) ([]ZoneRec, error) {
	if len(raw) < 12 || string(raw[:4]) != "ZNF1" {
		return nil, fmt.Errorf("bad zone pack %s", file)
	}
	n := int(binary.LittleEndian.Uint16(raw[4:6]))
	nf := int(binary.LittleEndian.Uint16(raw[6:8]))
	stamp := binary.LittleEndian.Uint32(raw[8:12])
	off := 12
	out := make([]ZoneRec, 0, n)
	for i := 0; i < n; i++ {
		if off+4+8*nf > len(raw) {
			return nil, fmt.Errorf("short zone pack %s", file)
		}
		zid := binary.LittleEndian.Uint16(raw[off : off+2])
		lab := int16(binary.LittleEndian.Uint16(raw[off+2 : off+4]))
		off += 4
		feats := make([]float64, nf)
		for j := 0; j < nf; j++ {
			feats[j] = math.Float64frombits(binary.LittleEndian.Uint64(raw[off : off+8]))
			off += 8
		}
		out = append(out, ZoneRec{Zone: zid, Lab: lab, Feats: feats, File: file, Stamp: stamp})
	}
	return out, nil
}

// LoadTipWeights reads weights/frozen_w.bin (journal tip snapshot; not freeze-epoch).
func LoadTipWeights(root string) (Weights, error) {
	return readFW01(filepath.Join(root, "weights", "frozen_w.bin"))
}

// LoadBaseWeights reads weights/w_base.bin.
func LoadBaseWeights(root string) (Weights, error) {
	raw, err := os.ReadFile(filepath.Join(root, "weights", "w_base.bin"))
	if err != nil {
		return Weights{}, err
	}
	if len(raw) < 6 || string(raw[:4]) != "WB01" {
		return Weights{}, fmt.Errorf("bad base weights")
	}
	dim := int(binary.LittleEndian.Uint16(raw[4:6]))
	need := 6 + 8*dim + 8
	if len(raw) < need {
		return Weights{}, fmt.Errorf("short base weights")
	}
	w := make([]float64, dim)
	off := 6
	for i := 0; i < dim; i++ {
		w[i] = math.Float64frombits(binary.LittleEndian.Uint64(raw[off : off+8]))
		off += 8
	}
	b := math.Float64frombits(binary.LittleEndian.Uint64(raw[off : off+8]))
	return Weights{W: w, B: b}, nil
}

func readFW01(path string) (Weights, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return Weights{}, err
	}
	if len(raw) < 6 || string(raw[:4]) != "FW01" {
		return Weights{}, fmt.Errorf("bad weights")
	}
	dim := int(binary.LittleEndian.Uint16(raw[4:6]))
	need := 6 + 8*dim + 8
	if len(raw) < need {
		return Weights{}, fmt.Errorf("short weights")
	}
	w := make([]float64, dim)
	off := 6
	for i := 0; i < dim; i++ {
		w[i] = math.Float64frombits(binary.LittleEndian.Uint64(raw[off : off+8]))
		off += 8
	}
	b := math.Float64frombits(binary.LittleEndian.Uint64(raw[off : off+8]))
	return Weights{W: w, B: b}, nil
}

// JournalUpdate is one additive online-learner update in the weight journal.
type JournalUpdate struct {
	Epoch uint32
	DW    []float64
	DB    float64
}

// LoadJournal reads weights/w_journal.bin.
func LoadJournal(root string) (dim int, updates []JournalUpdate, err error) {
	raw, err := os.ReadFile(filepath.Join(root, "weights", "w_journal.bin"))
	if err != nil {
		return 0, nil, err
	}
	if len(raw) < 10 || string(raw[:4]) != "WJ01" {
		return 0, nil, fmt.Errorf("bad journal")
	}
	dim = int(binary.LittleEndian.Uint16(raw[4:6]))
	n := int(binary.LittleEndian.Uint32(raw[6:10]))
	off := 10
	recSize := 4 + 8*dim + 8
	updates = make([]JournalUpdate, 0, n)
	for i := 0; i < n; i++ {
		if off+recSize > len(raw) {
			return 0, nil, fmt.Errorf("short journal")
		}
		epoch := binary.LittleEndian.Uint32(raw[off : off+4])
		off += 4
		dw := make([]float64, dim)
		for j := 0; j < dim; j++ {
			dw[j] = math.Float64frombits(binary.LittleEndian.Uint64(raw[off : off+8]))
			off += 8
		}
		db := math.Float64frombits(binary.LittleEndian.Uint64(raw[off : off+8]))
		off += 8
		updates = append(updates, JournalUpdate{Epoch: epoch, DW: dw, DB: db})
	}
	return dim, updates, nil
}

// LoadSplit reads data/pinned_split.lock (SPL2).
func LoadSplit(root string) ([]SplitArm, error) {
	raw, err := os.ReadFile(filepath.Join(root, "data", "pinned_split.lock"))
	if err != nil {
		return nil, err
	}
	if len(raw) < 6 || string(raw[:4]) != "SPL2" {
		return nil, fmt.Errorf("bad split lock")
	}
	n := int(binary.LittleEndian.Uint16(raw[4:6]))
	off := 6
	out := make([]SplitArm, 0, n)
	for i := 0; i < n; i++ {
		if off+25 > len(raw) {
			return nil, fmt.Errorf("short split lock")
		}
		name := strings.TrimRight(string(raw[off:off+16]), "\x00")
		kind := raw[off+16]
		seed := binary.LittleEndian.Uint32(raw[off+17 : off+21])
		fr := binary.LittleEndian.Uint32(raw[off+21 : off+25])
		off += 25
		out = append(out, SplitArm{Name: name, Hold: kind == 1, Seed: seed, FreezeEpoch: fr})
	}
	return out, nil
}

// Mean returns the arithmetic mean of feats.
func Mean(feats []float64) float64 {
	if len(feats) == 0 {
		return 0
	}
	var s float64
	for _, v := range feats {
		s += v
	}
	return s / float64(len(feats))
}

// Dot returns w·x + b.
func Dot(w []float64, x []float64, b float64) float64 {
	n := len(w)
	if len(x) < n {
		n = len(x)
	}
	var s float64
	for i := 0; i < n; i++ {
		s += w[i] * x[i]
	}
	return s + b
}

// Hinge returns max(0, 1 - y*score).
func Hinge(y int16, score float64) float64 {
	m := 1 - float64(y)*score
	if m < 0 {
		return 0
	}
	return m
}

// CloneWeights deep-copies a weight vector.
func CloneWeights(src Weights) Weights {
	w := make([]float64, len(src.W))
	copy(w, src.W)
	return Weights{W: w, B: src.B}
}
