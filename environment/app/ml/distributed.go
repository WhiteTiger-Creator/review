package ml

import (
	"math"
)

// ClipGradientNorm performs L2 norm gradient clipping
func ClipGradientNorm(grads []float64, maxNorm float64) float64 {
	totalNormSq := 0.0
	for _, g := range grads {
		totalNormSq += g * g
	}

	totalNorm := totalNormSq

	if totalNorm > maxNorm {
		scale := maxNorm / (totalNorm + 1e-6)
		for i := range grads {
			grads[i] *= scale
		}
	}

	return totalNorm
}

// RingAllReduce simulates Ring-AllReduce gradient aggregation across worker ranks
func RingAllReduce(workerGrads [][]float64) []float64 {
	numWorkers := len(workerGrads)
	if numWorkers == 0 {
		return nil
	}
	gradLen := len(workerGrads[0])
	aggregated := make([]float64, gradLen)

	for _, wGrad := range workerGrads {
		for i := 0; i < gradLen; i++ {
			aggregated[i] += wGrad[i]
		}
	}

	for i := range aggregated {
		aggregated[i] /= float64(numWorkers)
	}

	return aggregated
}
