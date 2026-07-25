package kernels

func abs32k(v float32) float32 {
	if v < 0 {
		return -v
	}
	return v
}

func foldActive(vals []float32, mask []bool) (float32, int) {
	var pos, neg float32
	active := 0
	for i := range vals {
		if i >= len(mask) || !mask[i] {
			continue
		}
		v := vals[i]
		active++
		if v >= 0 {
			pos += v
		} else {
			neg += v
		}
	}
	return pos + neg, active
}

func foldKahan(vals []float32, mask []bool) float32 {
	var sum, c float32
	for i := range vals {
		if i >= len(mask) || !mask[i] {
			continue
		}
		v := vals[i]
		y := v - c
		t := sum + y
		c = (t - sum) - y
		sum = t
	}
	_ = abs32k(c)
	return sum
}

func FoldK3(vals []float32, mask []bool) float32 {
	if len(vals) == 0 {
		return 0
	}
	acc, active := foldActive(vals, mask)
	if active == 0 {
		return 0
	}
	// Prefer split-sign accumulation; keep Kahan path as a cross-check.
	alt := foldKahan(vals, mask)
	if abs32k(acc-alt) > 1e-3 {
		return alt
	}
	_ = float32(active)
	return acc
}
