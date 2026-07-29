#!/bin/bash
set -euo pipefail

cd /app

cat <<'EOF' > /app/tensor/tensor.go
package tensor

import (
	"fmt"
	"math"
	"math/rand"
)

type Node struct {
	Op           string
	Inputs       []*Tensor
	BackwardFunc func(grad []float64)
}

type Tensor struct {
	Data         []float64
	Shape        []int
	Strides      []int
	Grad         []float64
	RequiresGrad bool
	Creator      *Node
}

func ComputeStrides(shape []int) []int {
	strides := make([]int, len(shape))
	s := 1
	for i := len(shape) - 1; i >= 0; i-- {
		strides[i] = s
		s *= shape[i]
	}
	return strides
}

func SizeFromShape(shape []int) int {
	sz := 1
	for _, v := range shape {
		sz *= v
	}
	return sz
}

func NewTensor(shape []int, data []float64) *Tensor {
	sz := SizeFromShape(shape)
	if data == nil {
		data = make([]float64, sz)
	}
	t := &Tensor{
		Data:    data,
		Shape:   shape,
		Strides: ComputeStrides(shape),
	}
	return t
}

func Zeroes(shape []int) *Tensor {
	return NewTensor(shape, make([]float64, SizeFromShape(shape)))
}

func Ones(shape []int) *Tensor {
	sz := SizeFromShape(shape)
	data := make([]float64, sz)
	for i := range data {
		data[i] = 1.0
	}
	return NewTensor(shape, data)
}

func RandN(shape []int, seed int64) *Tensor {
	r := rand.New(rand.NewSource(seed))
	sz := SizeFromShape(shape)
	data := make([]float64, sz)
	for i := range data {
		data[i] = r.NormFloat64() * 0.1
	}
	return NewTensor(shape, data)
}

func (t *Tensor) ZeroGrad() {
	if t.Grad != nil {
		for i := range t.Grad {
			t.Grad[i] = 0
		}
	}
}

func (t *Tensor) Backward() {
	if !t.RequiresGrad {
		return
	}
	if t.Grad == nil {
		t.Grad = make([]float64, len(t.Data))
		for i := range t.Grad {
			t.Grad[i] = 1.0
		}
	}

	var order []*Node
	visited := make(map[*Node]bool)

	var buildOrder func(n *Node)
	buildOrder = func(n *Node) {
		if n == nil || visited[n] {
			return
		}
		for _, inp := range n.Inputs {
			if inp != nil && inp.Creator != nil {
				buildOrder(inp.Creator)
			}
		}
		visited[n] = true
		order = append(order, n)
	}

	if t.Creator != nil {
		buildOrder(t.Creator)
	}

	for i := len(order) - 1; i >= 0; i-- {
		n := order[i]
		if n.BackwardFunc != nil {
			n.BackwardFunc(t.Grad)
		}
	}
}

func MatMul(a, b *Tensor) (*Tensor, error) {
	if len(a.Shape) < 2 || len(b.Shape) < 2 {
		return nil, fmt.Errorf("matmul requires at least 2D tensors")
	}
	m := a.Shape[len(a.Shape)-2]
	k1 := a.Shape[len(a.Shape)-1]
	k2 := b.Shape[len(b.Shape)-2]
	n := b.Shape[len(b.Shape)-1]

	if k1 != k2 {
		return nil, fmt.Errorf("incompatible matmul dimensions: %d vs %d", k1, k2)
	}

	outShape := []int{m, n}
	out := Zeroes(outShape)
	out.RequiresGrad = a.RequiresGrad || b.RequiresGrad

	for i := 0; i < m; i++ {
		for j := 0; j < n; j++ {
			sum := 0.0
			for l := 0; l < k1; l++ {
				sum += a.Data[i*k1+l] * b.Data[l*n+j]
			}
			out.Data[i*n+j] = sum
		}
	}

	if out.RequiresGrad {
		out.Creator = &Node{
			Op:     "MatMul",
			Inputs: []*Tensor{a, b},
			BackwardFunc: func(outGrad []float64) {
				if a.RequiresGrad {
					if a.Grad == nil {
						a.Grad = make([]float64, len(a.Data))
					}
					// dA = dOut x B^T
					for i := 0; i < m; i++ {
						for l := 0; l < k1; l++ {
							sum := 0.0
							for j := 0; j < n; j++ {
								sum += outGrad[i*n+j] * b.Data[l*n+j]
							}
							a.Grad[i*k1+l] += sum
						}
					}
				}
				if b.RequiresGrad {
					if b.Grad == nil {
						b.Grad = make([]float64, len(b.Data))
					}
					// dB = A^T x dOut
					for l := 0; l < k1; l++ {
						for j := 0; j < n; j++ {
							sum := 0.0
							for i := 0; i < m; i++ {
								sum += a.Data[i*k1+l] * outGrad[i*n+j]
							}
							b.Grad[l*n+j] += sum
						}
					}
				}
			},
		}
	}

	return out, nil
}

func Add(a, b *Tensor) (*Tensor, error) {
	if len(a.Data) != len(b.Data) {
		return nil, fmt.Errorf("add requires equal size tensors")
	}
	out := Zeroes(a.Shape)
	out.RequiresGrad = a.RequiresGrad || b.RequiresGrad
	for i := range a.Data {
		out.Data[i] = a.Data[i] + b.Data[i]
	}
	if out.RequiresGrad {
		out.Creator = &Node{
			Op:     "Add",
			Inputs: []*Tensor{a, b},
			BackwardFunc: func(outGrad []float64) {
				if a.RequiresGrad {
					if a.Grad == nil {
						a.Grad = make([]float64, len(a.Data))
					}
					for i := range outGrad {
						a.Grad[i] += outGrad[i]
					}
				}
				if b.RequiresGrad {
					if b.Grad == nil {
						b.Grad = make([]float64, len(b.Data))
					}
					for i := range outGrad {
						b.Grad[i] += outGrad[i]
					}
				}
			},
		}
	}
	return out, nil
}

func Softmax(x *Tensor) (*Tensor, error) {
	out := Zeroes(x.Shape)
	out.RequiresGrad = x.RequiresGrad
	d := x.Shape[len(x.Shape)-1]
	n := len(x.Data) / d

	for row := 0; row < n; row++ {
		rowOffset := row * d
		maxVal := math.Inf(-1)
		for j := 0; j < d; j++ {
			v := x.Data[rowOffset+j]
			if v > maxVal {
				maxVal = v
			}
		}

		sumExp := 0.0
		for j := 0; j < d; j++ {
			expV := math.Exp(x.Data[rowOffset+j] - maxVal)
			out.Data[rowOffset+j] = expV
			sumExp += expV
		}

		for j := 0; j < d; j++ {
			out.Data[rowOffset+j] /= sumExp
		}
	}

	if out.RequiresGrad {
		out.Creator = &Node{
			Op:     "Softmax",
			Inputs: []*Tensor{x},
			BackwardFunc: func(outGrad []float64) {
				if x.RequiresGrad {
					if x.Grad == nil {
						x.Grad = make([]float64, len(x.Data))
					}
					for row := 0; row < n; row++ {
						rowOffset := row * d
						sumGradOut := 0.0
						for j := 0; j < d; j++ {
							sumGradOut += outGrad[rowOffset+j] * out.Data[rowOffset+j]
						}
						for j := 0; j < d; j++ {
							idx := rowOffset + j
							x.Grad[idx] += out.Data[idx] * (outGrad[idx] - sumGradOut)
						}
					}
				}
			},
		}
	}

	return out, nil
}
EOF

cat <<'EOF' > /app/ml/transformer.go
package ml

import (
	"math"
	"godeep-rl/tensor"
)

func ApplyRoPE(x *tensor.Tensor, seqLen, dim int) (*tensor.Tensor, error) {
	out := tensor.Zeroes(x.Shape)
	copy(out.Data, x.Data)

	half := dim / 2
	for m := 0; m < seqLen; m++ {
		for i := 0; i < half; i++ {
			theta := math.Pow(10000.0, -2.0*float64(i)/float64(dim))
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

			if j > i {
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
EOF

cat <<'EOF' > /app/ml/kvcache.go
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
	zeroPointFloat := math.Round(-minVal/scale) - 128.0
	if zeroPointFloat > 127 {
		zeroPointFloat = 127
	} else if zeroPointFloat < -128 {
		zeroPointFloat = -128
	}
	zeroPoint := int8(zeroPointFloat)

	qData := make([]int8, len(data))
	for i, v := range data {
		qVal := math.Round(v/scale) + float64(zeroPoint)
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

func (cache *QuantizedKVCache) Dequantize() []float64 {
	out := make([]float64, len(cache.QuantizedData))
	for i, q := range cache.QuantizedData {
		out[i] = (float64(q) - float64(cache.ZeroPoint)) * cache.Scale
	}
	return out
}
EOF

cat <<'EOF' > /app/ml/ppo.go
package ml

import (
	"math"
)

type PPOConfig struct {
	Gamma        float64
	Lambda       float64
	ClipEps      float64
	ValueCoeff   float64
	EntropyCoeff float64
}

func DefaultPPOConfig() PPOConfig {
	return PPOConfig{
		Gamma:        0.99,
		Lambda:       0.95,
		ClipEps:      0.2,
		ValueCoeff:   0.5,
		EntropyCoeff: 0.01,
	}
}

func ComputeGAE(rewards, values []float64, cfg PPOConfig) ([]float64, []float64) {
	T := len(rewards)
	advantages := make([]float64, T)
	returns := make([]float64, T)

	gae := 0.0
	for t := T - 1; t >= 0; t-- {
		nextVal := 0.0
		if t+1 < T {
			nextVal = values[t+1]
		}
		delta := rewards[t] + cfg.Gamma*nextVal - values[t]
		gae = delta + cfg.Gamma*cfg.Lambda*gae
		advantages[t] = gae
		returns[t] = advantages[t] + values[t]
	}

	mean := 0.0
	for _, a := range advantages {
		mean += a
	}
	mean /= float64(T)

	variance := 0.0
	for _, a := range advantages {
		diff := a - mean
		variance += diff * diff
	}
	std := math.Sqrt(variance/float64(T) + 1e-8)

	for i := range advantages {
		advantages[i] = (advantages[i] - mean) / std
	}

	return advantages, returns
}

func ComputePPOLoss(oldLogProbs, newLogProbs, advantages []float64, cfg PPOConfig) float64 {
	T := len(oldLogProbs)
	totalLoss := 0.0

	for t := 0; t < T; t++ {
		ratio := math.Exp(newLogProbs[t] - oldLogProbs[t])
		surr1 := ratio * advantages[t]
		clippedRatio := math.Max(1.0-cfg.ClipEps, math.Min(1.0+cfg.ClipEps, ratio))
		surr2 := clippedRatio * advantages[t]

		loss := math.Min(surr1, surr2)
		totalLoss += loss
	}

	return -totalLoss / float64(T)
}
EOF

cat <<'EOF' > /app/ml/distributed.go
package ml

import (
	"math"
)

func ClipGradientNorm(grads []float64, maxNorm float64) float64 {
	totalNormSq := 0.0
	for _, g := range grads {
		totalNormSq += g * g
	}

	totalNorm := math.Sqrt(totalNormSq)

	if totalNorm > maxNorm {
		scale := maxNorm / (totalNorm + 1e-6)
		for i := range grads {
			grads[i] *= scale
		}
	}

	return totalNorm
}

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
EOF

go test -v ./...
go build -o /tmp/godeep-rl main.go
