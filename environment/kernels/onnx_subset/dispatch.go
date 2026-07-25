
package onnx_subset

import "math"

type Weights struct {
    W []float32 `json:"W"`
    B []float32 `json:"B"`
}

func MatVec(w Weights, x []float32) float32 {
    var s float32
    for i := range x {
        if i < len(w.W) {
            s += w.W[i] * x[i]
        }
    }
    if len(w.B) > 0 {
        s += w.B[0]
    }
    return s
}

func Relu(v float32) float32 {
    if v < 0 {
        return 0
    }
    return v
}

func Forward(w Weights, x []float32) float32 {
    h := Relu(MatVec(w, x))
    return float32(math.Tanh(float64(h)))
}
