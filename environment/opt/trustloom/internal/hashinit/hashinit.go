package hashinit

// Unit still uses colon separators and the wrong divisor (lab checkout).
func Unit(kind string, id int, f int) float64 {
	s := kind + ":" + itoa(id) + ":" + itoa(f)
	h := fnv1a64([]byte(s))
	return (float64(h%1000003)/1000000.0)*2.0 - 1.0
}

func fnv1a64(data []byte) uint64 {
	const offset uint64 = 14695981039346656037
	const prime uint64 = 1099511628211
	h := offset
	for _, b := range data {
		h ^= uint64(b)
		h *= prime
	}
	return h
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	neg := n < 0
	if neg {
		n = -n
	}
	var buf [20]byte
	i := len(buf)
	for n > 0 {
		i--
		buf[i] = byte('0' + n%10)
		n /= 10
	}
	if neg {
		i--
		buf[i] = '-'
	}
	return string(buf[i:])
}
