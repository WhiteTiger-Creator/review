package frontprep

import (
	"math"

	"github.com/local/etaengine/types"
)

const peakFloor = float32(1e-9)

func abs32(v float32) float32 {
	if v < 0 {
		return -v
	}
	return v
}

func finite32(v float32) bool {
	return !math.IsNaN(float64(v)) && !math.IsInf(float64(v), 0)
}

func peakAbs(rows [][]float32) float32 {
	peak := peakFloor
	for _, row := range rows {
		for _, v := range row {
			if !finite32(v) {
				continue
			}
			av := abs32(v)
			if av > peak {
				peak = av
			}
		}
	}
	if peak < peakFloor {
		return peakFloor
	}
	return peak
}

func OpA2(rows [][]float32, caps *types.FieldCaps, mode string) []float32 {
	scales := make([]float32, caps.Fields)
	if mode == "declared" {
		base := caps.DeclaredScale
		if base <= 0 {
			base = 1
		}
		inv := float32(1.0) / base
		for i := range scales {
			scales[i] = inv
		}
		return scales
	}
	global := peakAbs(rows)
	for i := range scales {
		scales[i] = float32(1.0) / global
	}
	return scales
}

func ApplyScale(rows [][]float32, scales []float32) [][]float32 {
	out := make([][]float32, len(rows))
	for i, row := range rows {
		r := make([]float32, len(row))
		for j, v := range row {
			idx := j
			if idx >= len(scales) {
				idx = len(scales) - 1
			}
			if idx < 0 {
				r[j] = v
				continue
			}
			r[j] = v * scales[idx]
		}
		out[i] = r
	}
	return out
}
