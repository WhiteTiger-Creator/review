package kernels

func FoldPairwise(vals []float32, mask []bool) float32 {
    var pos, neg float32
    for i := range vals {
        if i >= len(mask) || !mask[i] {
            continue
        }
        v := vals[i]
        if v >= 0 {
            pos += v
        } else {
            neg += v
        }
    }
    return pos + neg
}
