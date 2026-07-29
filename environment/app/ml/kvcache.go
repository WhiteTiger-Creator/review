package ml

import (
	"math"
)

type QuantizedKVCache struct {
	QuantizedData []int8
	Scale         float64
	ZeroPoint     int8
	SeqLen        int
	Dim           int
}

// QuantizeAsymmetricINT8 quantizes float64 slice to INT8 asymmetric representation
func QuantizeAsymmetricINT8(data []float64, seqLen, dim int) *QuantizedKVCache {
	minVal := math.Inf(1)
	maxVal := math.Inf(-1)

	for _, v := range data {
		if v < minVal {
			minVal = v
		}
		if v > maxVal {
			maxVal = v
		}
	}

	if maxVal == minVal {
		maxVal = minVal + 1e-6
	}

	scale := (maxVal - minVal) / 255.0
	zeroPointFloat := (-minVal / scale)
	zeroPoint := int8(zeroPointFloat)

	qData := make([]int8, len(data))
	for i, v := range data {
		qVal := math.Round((v / scale) + float64(zeroPoint))
		if qVal > 127 {
			qVal = 127
		} else if qVal < -128 {
			qVal = -128
		}
		qData[i] = int8(qVal)
	}

	return &QuantizedKVCache{
		QuantizedData: qData,
		Scale:         scale,
		ZeroPoint:     zeroPoint,
		SeqLen:        seqLen,
		Dim:           dim,
	}
}

// Dequantize converts INT8 quantized KV cache back to float64 slice
func (cache *QuantizedKVCache) Dequantize() []float64 {
	out := make([]float64, len(cache.QuantizedData))
	for i, q := range cache.QuantizedData {
		out[i] = (float64(q) - float64(cache.ZeroPoint)) * cache.Scale
	}
	return out
}
