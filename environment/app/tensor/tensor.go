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
					for i := 0; i < m; i++ {
						for l := 0; l < k1; l++ {
							sum := 0.0
							for j := 0; j < n; j++ {
								sum += outGrad[i*n+j] * b.Data[j*k2+l]
							}
							a.Grad[i*k1+l] += sum
						}
					}
				}
				if b.RequiresGrad {
					if b.Grad == nil {
						b.Grad = make([]float64, len(b.Data))
					}
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
							x.Grad[idx] += out.Data[idx] * sumGradOut
						}
					}
				}
			},
		}
	}

	return out, nil
}
