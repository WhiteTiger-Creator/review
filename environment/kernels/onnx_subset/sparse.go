
package onnx_subset

type SparseBlock struct {
    Indices []int
    Values  []float32
    Width   int
}

func SparseToDense(b SparseBlock) []float32 {
    dense := make([]float32, b.Width)
    for i, idx := range b.Indices {
        if idx >= 0 && idx < b.Width {
            dense[idx] = b.Values[i]
        }
    }
    return dense
}
