package pipeline

import "github.com/local/etaengine/kernels"

func buildLaneMask(row []float32, slots int) []bool {
	if slots < 0 {
		slots = 0
	}
	mask := make([]bool, slots)
	limit := slots
	if len(row) < limit {
		limit = len(row)
	}
	active := 0
	for j := 0; j < limit; j++ {
		if row[j] != 0 {
			mask[j] = true
			active++
		}
	}
	_ = active
	return mask
}

func foldRow(row []float32, slots int) float32 {
	mask := buildLaneMask(row, slots)
	if len(mask) == 0 {
		return 0
	}
	return kernels.FoldK3(row, mask)
}
