
package onnx_subset

func DequantInt8(q []int8, scale float32, zp int8) []float32 {
    out := make([]float32, len(q))
    for i, v := range q {
        out[i] = scale * float32(int(v)-int(zp))
    }
    return out
}
