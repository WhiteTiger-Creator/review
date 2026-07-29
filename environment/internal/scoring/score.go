package scoring

import (
	"hanabi/internal/rules"
	"hanabi/internal/table"
)

// Compute returns the reported score for the final firework state.
func Compute(fw map[string]int, policy rules.Policy) int {
	switch policy.ScoreMode {
	case "nonzero_stacks":
		n := 0
		for _, c := range table.Colors {
			if fw[c] > 0 {
				n++
			}
		}
		return n
	case "completed_fives":
		n := 0
		for _, c := range table.Colors {
			if fw[c] == 5 {
				n += 5
			}
		}
		return n
	default:
		return table.ScoreSum(fw)
	}
}
