package feed

// At returns whether the press bit is set on frame i.
func At(frames []int, i int) bool {
	if i < 0 || i >= len(frames) {
		return false
	}
	return frames[i] != 0
}
