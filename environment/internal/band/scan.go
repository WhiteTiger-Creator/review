package band

// Hist is a debug occupancy histogram for the ops smoke path.
func Hist(tops []float64, y float64, skin float64) []int {
	out := make([]int, len(tops))
	for i, t := range tops {
		if y >= t && y <= t+skin {
			out[i] = 1
		}
	}
	return out
}
