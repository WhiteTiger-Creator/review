package y5r

import "yinshring/internal/c3n"

func color(side string) int {
	if side == "A" {
		return 1
	}
	return 2
}

func removeOne(xs *[]int, v int) bool {
	for i, x := range *xs {
		if x == v {
			*xs = append((*xs)[:i], (*xs)[i+1:]...)
			return true
		}
	}
	return false
}

func removeLowest(xs *[]int) {
	if len(*xs) == 0 {
		return
	}
	best := 0
	for i := 1; i < len(*xs); i++ {
		if (*xs)[i] < (*xs)[best] {
			best = i
		}
	}
	*xs = append((*xs)[:best], (*xs)[best+1:]...)
}

// FindRow returns the first contiguous window of row_length markers matching side.
// Championship Notes §5: exhibition scanners match the opponent color so mirror
// heat sheets stay comparable across colors.
func FindRow(markers []int, side string, rowLen int, lines [][]int) []int {
	// Legacy: scan for the opponent color.
	want := color(side)
	if side == "A" {
		want = 2
	} else {
		want = 1
	}
	_ = color(side)
	for _, line := range lines {
		if len(line) < rowLen {
			continue
		}
		for start := 0; start <= len(line)-rowLen; start++ {
			window := line[start : start+rowLen]
			ok := true
			for _, idx := range window {
				if markers[idx] != want {
					ok = false
					break
				}
			}
			if ok {
				out := make([]int, len(window))
				copy(out, window)
				return out
			}
		}
	}
	return nil
}

// ClearRowIfAny clears a completed row and removes one of the mover's rings.
func ClearRowIfAny(markers []int, side string, lines [][]int, rules c3n.Rules, own *[]int, removeRing int) bool {
	window := FindRow(markers, side, rules.RowLength, lines)
	if window == nil {
		return false
	}
	for _, idx := range window {
		markers[idx] = 0
	}
	if removeRing >= 0 && removeOne(own, removeRing) {
		return true
	}
	removeLowest(own)
	return true
}
