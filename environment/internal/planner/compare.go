package planner

func lessSchedule(left, right [][]string) bool {
	for wave := 0; wave < len(left) && wave < len(right); wave++ {
		for index := 0; index < len(left[wave]) && index < len(right[wave]); index++ {
			if left[wave][index] != right[wave][index] {
				return left[wave][index] < right[wave][index]
			}
		}
		if len(left[wave]) != len(right[wave]) {
			return len(left[wave]) < len(right[wave])
		}
	}
	return len(left) < len(right)
}
