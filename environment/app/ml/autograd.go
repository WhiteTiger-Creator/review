package ml

import (
	"math"
	"godeep-rl/tensor"
)

// GELU activation function: 0.5 * x * (1 + tanh(sqrt(2/pi) * (x + 0.044715 * x^3)))
func GELU(x *tensor.Tensor) (*tensor.Tensor, error) {
	out := tensor.Zeroes(x.Shape)
	out.RequiresGrad = x.RequiresGrad
	const c = 0.7978845608028654 // sqrt(2/pi)

	for i, v := range x.Data {
		cdf := 0.5 * (1.0 + math.Tanh(c*(v+0.044715*math.Pow(v, 3))))
		out.Data[i] = v * cdf
	}

	if out.RequiresGrad {
		out.Creator = &tensor.Node{
			Op:     "GELU",
			Inputs: []*tensor.Tensor{x},
			BackwardFunc: func(outGrad []float64) {
				if x.RequiresGrad {
					if x.Grad == nil {
						x.Grad = make([]float64, len(x.Data))
					}
					for i, v := range x.Data {
						inner := c * (v + 0.044715*math.Pow(v, 3))
						tanhVal := math.Tanh(inner)
						dtanh := c * (1.0 + 3.0*0.044715*v*v) * (1.0 - tanhVal*tanhVal)
						dGELU := 0.5*(1.0+tanhVal) + 0.5*v*dtanh
						x.Grad[i] += outGrad[i] * dGELU
					}
				}
			},
		}
	}
	return out, nil
}

// LayerNorm performs layer normalization across the final dimension
func LayerNorm(x *tensor.Tensor, gamma, beta []float64, eps float64) (*tensor.Tensor, error) {
	out := tensor.Zeroes(x.Shape)
	out.RequiresGrad = x.RequiresGrad
	d := x.Shape[len(x.Shape)-1]
	n := len(x.Data) / d

	means := make([]float64, n)
	vars := make([]float64, n)

	for i := 0; i < n; i++ {
		sum := 0.0
		for j := 0; j < d; j++ {
			sum += x.Data[i*d+j]
		}
		mean := sum / float64(d)
		means[i] = mean

		varSum := 0.0
		for j := 0; j < d; j++ {
			diff := x.Data[i*d+j] - mean
			varSum += diff * diff
		}
		variance := varSum / float64(d)
		vars[i] = variance

		invStd := 1.0 / math.Sqrt(variance+eps)
		for j := 0; j < d; j++ {
			norm := (x.Data[i*d+j] - mean) * invStd
			out.Data[i*d+j] = norm*gamma[j] + beta[j]
		}
	}

	return out, nil
}
