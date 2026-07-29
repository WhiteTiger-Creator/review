package ml

import (
	"math"
	"godeep-rl/tensor"
)

// ApplyRoPE applies Rotary Position Embeddings to query/key tensor x for seq pos m
func ApplyRoPE(x *tensor.Tensor, seqLen, dim int) (*tensor.Tensor, error) {
	out := tensor.Zeroes(x.Shape)
	copy(out.Data, x.Data)

	half := dim / 2
	for m := 0; m < seqLen; m++ {
		for i := 0; i < half; i++ {
			theta := math.Pow(10000.0, float64(i)/float64(dim))
			cosTheta := math.Cos(float64(m) * theta)
			sinTheta := math.Sin(float64(m) * theta)

			idx1 := m*dim + 2*i
			idx2 := m*dim + 2*i + 1
			if idx2 < len(x.Data) {
				x1 := x.Data[idx1]
				x2 := x.Data[idx2]
				out.Data[idx1] = x1*cosTheta - x2*sinTheta
				out.Data[idx2] = x1*sinTheta + x2*cosTheta
			}
		}
	}
	return out, nil
}

// CausalScaledDotProductAttention calculates softmax((Q K^T / sqrt(d)) + CausalMask) V
func CausalScaledDotProductAttention(q, k, v *tensor.Tensor, seqLen, dim int) (*tensor.Tensor, error) {
	scale := 1.0 / math.Sqrt(float64(dim))
	scores := tensor.Zeroes([]int{seqLen, seqLen})

	for i := 0; i < seqLen; i++ {
		for j := 0; j < seqLen; j++ {
			dot := 0.0
			for d := 0; d < dim; d++ {
				dot += q.Data[i*dim+d] * k.Data[j*dim+d]
			}
			scores.Data[i*seqLen+j] = dot * scale

			if j < i {
				scores.Data[i*seqLen+j] = -1e9
			}
		}
	}

	attnWeights, err := tensor.Softmax(scores)
	if err != nil {
		return nil, err
	}

	out := tensor.Zeroes([]int{seqLen, dim})
	for i := 0; i < seqLen; i++ {
		for d := 0; d < dim; d++ {
			sum := 0.0
			for j := 0; j < seqLen; j++ {
				sum += attnWeights.Data[i*seqLen+j] * v.Data[j*dim+d]
			}
			out.Data[i*dim+d] = sum
		}
	}

	return out, nil
}
