
package onnx_subset

type Tensor struct {
    Data  []float32
    Shape []int
}

func NewTensor(shape []int, data []float32) *Tensor {
    return &Tensor{Data: data, Shape: shape}
}
