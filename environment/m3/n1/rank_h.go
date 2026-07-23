package n1

// HMul and LMul are binder knobs set by the package facade before ranking.
var HMul uint32 = 65521
var LMul uint32 = 127

// fn_h7 produces a ranking vector from schedule hints and slot indices.
func fn_h7(hints []uint32, layerIx []uint16) []uint32 {
	n := len(hints)
	if len(layerIx) < n {
		n = len(layerIx)
	}
	scores := make([]uint32, n)
	for i := 0; i < n; i++ {
		scores[i] = hints[i] * HMul
	}
	order := make([]int, n)
	for i := range order {
		order[i] = i
	}
	for i := 1; i < n; i++ {
		j := i
		for j > 0 {
			pj, pj1 := order[j-1], order[j]
			if scores[pj] < scores[pj1] || (scores[pj] == scores[pj1] && pj > pj1) {
				order[j-1], order[j] = order[j], order[j-1]
				j--
				continue
			}
			break
		}
	}
	ranks := make([]uint32, n)
	for pos, idx := range order {
		ranks[idx] = uint32(pos)
	}
	return ranks
}

// ApplyRank sets binders then invokes fn_h7.
func ApplyRank(hints []uint32, layerIx []uint16, hintMul, laneMul uint32) []uint32 {
	HMul = hintMul
	LMul = laneMul
	return fn_h7(hints, layerIx)
}
