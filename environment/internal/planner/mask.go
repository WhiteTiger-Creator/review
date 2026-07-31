package planner

func bitCount(mask uint16) int {
	count := 0
	for mask != 0 {
		count += int(mask & 1)
		mask >>= 1
	}
	return count
}

func (ctx context) names(mask uint16) []string {
	values := make([]string, 0, bitCount(mask))
	for index, id := range ctx.targets {
		if mask&(uint16(1)<<index) != 0 {
			values = append(values, id)
		}
	}
	return values
}
