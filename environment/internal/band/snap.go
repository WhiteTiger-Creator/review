package band

func Snap(a float64, b float64, c float64, d float64) (float64, bool) {
	if d < 0 && a >= b && a <= b+c {
		return b, true
	}
	return a, false
}
