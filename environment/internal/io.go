package internal

import (
	"encoding/binary"
	"fmt"
	"math"
	"os"
)

// Rec is one decoded feature record.
type Rec struct {
	Id    uint16
	Role  uint8
	Feats []float64
	Ka    int16
	Kb    int16
	Lim   uint16
}

// Pin is the pinned packing order.
type Pin struct {
	Slice uint16
	Seed  uint32
	Order []uint16
}

// Wts is frozen linear weights.
type Wts struct {
	W    []float64
	Bias float64
}

// SplitPack separates concatenated FEAT|PIN1|WB01 bytes.
func SplitPack(pack []byte) (feat, pin, wts []byte, err error) {
	if len(pack) < 4 || string(pack[0:4]) != "FEAT" {
		return nil, nil, nil, fmt.Errorf("feat magic")
	}
	if len(pack) < 12 {
		return nil, nil, nil, fmt.Errorf("feat hdr")
	}
	n := int(binary.LittleEndian.Uint16(pack[4:6]))
	nf := int(binary.LittleEndian.Uint16(pack[6:8]))
	// stamp at 8:12
	rec := 2 + 1 + 1 + 8*nf + 2 + 2 + 2
	featEnd := 12 + n*rec
	if featEnd > len(pack) {
		return nil, nil, nil, fmt.Errorf("feat trunc")
	}
	feat = pack[:featEnd]
	rest := pack[featEnd:]
	if len(rest) < 4 || string(rest[0:4]) != "PIN1" {
		return nil, nil, nil, fmt.Errorf("pin magic")
	}
	if len(rest) < 12 {
		return nil, nil, nil, fmt.Errorf("pin hdr")
	}
	nc := int(binary.LittleEndian.Uint16(rest[10:12]))
	pinEnd := 12 + 2*nc
	if pinEnd > len(rest) {
		return nil, nil, nil, fmt.Errorf("pin trunc")
	}
	pin = rest[:pinEnd]
	wts = rest[pinEnd:]
	if len(wts) < 4 || string(wts[0:4]) != "WB01" {
		return nil, nil, nil, fmt.Errorf("wts magic")
	}
	return feat, pin, wts, nil
}

// ParseFeat decodes FEAT bytes.
func ParseFeat(b []byte) ([]Rec, error) {
	if len(b) < 12 || string(b[0:4]) != "FEAT" {
		return nil, fmt.Errorf("feat")
	}
	n := int(binary.LittleEndian.Uint16(b[4:6]))
	nf := int(binary.LittleEndian.Uint16(b[6:8]))
	out := make([]Rec, 0, n)
	off := 12
	for i := 0; i < n; i++ {
		need := 4 + 8*nf + 6
		if off+need > len(b) {
			return nil, fmt.Errorf("feat row")
		}
		id := binary.LittleEndian.Uint16(b[off : off+2])
		role := b[off+2]
		off += 4
		feats := make([]float64, nf)
		for j := 0; j < nf; j++ {
			feats[j] = math.Float64frombits(binary.LittleEndian.Uint64(b[off : off+8]))
			off += 8
		}
		ka := int16(binary.LittleEndian.Uint16(b[off : off+2]))
		kb := int16(binary.LittleEndian.Uint16(b[off+2 : off+4]))
		lim := binary.LittleEndian.Uint16(b[off+4 : off+6])
		off += 6
		out = append(out, Rec{Id: id, Role: role, Feats: feats, Ka: ka, Kb: kb, Lim: lim})
	}
	return out, nil
}

// ParsePin decodes PIN1 bytes.
func ParsePin(b []byte) (Pin, error) {
	var p Pin
	if len(b) < 12 || string(b[0:4]) != "PIN1" {
		return p, fmt.Errorf("pin")
	}
	p.Slice = binary.LittleEndian.Uint16(b[4:6])
	p.Seed = binary.LittleEndian.Uint32(b[6:10])
	nc := int(binary.LittleEndian.Uint16(b[10:12]))
	if 12+2*nc > len(b) {
		return p, fmt.Errorf("pin body")
	}
	p.Order = make([]uint16, nc)
	for i := 0; i < nc; i++ {
		p.Order[i] = binary.LittleEndian.Uint16(b[12+2*i : 14+2*i])
	}
	return p, nil
}

// ParseWts decodes WB01 bytes.
func ParseWts(b []byte) (Wts, error) {
	var w Wts
	if len(b) < 6 || string(b[0:4]) != "WB01" {
		return w, fmt.Errorf("wts")
	}
	dim := int(binary.LittleEndian.Uint16(b[4:6]))
	need := 6 + 8*dim + 8
	if len(b) < need {
		return w, fmt.Errorf("wts body")
	}
	w.W = make([]float64, dim)
	off := 6
	for i := 0; i < dim; i++ {
		w.W[i] = math.Float64frombits(binary.LittleEndian.Uint64(b[off : off+8]))
		off += 8
	}
	w.Bias = math.Float64frombits(binary.LittleEndian.Uint64(b[off : off+8]))
	return w, nil
}

// ReadFile is a thin os.ReadFile wrapper.
func ReadFile(path string) ([]byte, error) {
	return os.ReadFile(path)
}

// DotBias computes w·x + bias.
func DotBias(w []float64, x []float64, bias float64) float64 {
	n := len(w)
	if len(x) < n {
		n = len(x)
	}
	s := bias
	for i := 0; i < n; i++ {
		s += w[i] * x[i]
	}
	return s
}
