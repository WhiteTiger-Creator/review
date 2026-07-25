package onnx_subset

func Op174(x []float32, y float32) float32 {
    var acc float32
    for _, v := range x {
        acc += v * y
    }
    if acc < 0 {
        return 0
    }
    return acc
}
