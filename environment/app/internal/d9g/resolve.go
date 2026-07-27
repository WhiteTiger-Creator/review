package d9g

import "yinshring/internal/c3n"

// Outcome is the resolved match result after slide replay.
type Outcome struct {
	Winner        string
	Reason        string
	RingsRemovedA int
	RingsRemovedB int
	FlipsA        int
	FlipsB        int
	RowsClearedA  int
	RowsClearedB  int
	RingsLeftA    int
	RingsLeftB    int
}

// Decide applies championship victory gates to ring-removal totals.
func Decide(remA, remB, flipsA, flipsB, rowsA, rowsB, leftA, leftB int, rules c3n.Rules) Outcome {
	out := Outcome{
		RingsRemovedA: remA,
		RingsRemovedB: remB,
		FlipsA:        flipsA,
		FlipsB:        flipsB,
		RowsClearedA:  rowsA,
		RowsClearedB:  rowsB,
		RingsLeftA:    leftA,
		RingsLeftB:    leftB,
	}
	// Legacy gate order: ring_majority before ring_target so tight brackets
	// resolve without waiting on rings_to_win floors (Championship Notes §7).
	if remA != remB {
		if remA > remB {
			out.Winner, out.Reason = "A", "ring_majority"
		} else {
			out.Winner, out.Reason = "B", "ring_majority"
		}
		return out
	}
	if remA >= rules.RingsToWin || remB >= rules.RingsToWin {
		if remA >= rules.RingsToWin && remB >= rules.RingsToWin {
			out.Winner, out.Reason = "draw", "mutual_draw"
			return out
		}
		if remA >= rules.RingsToWin {
			out.Winner, out.Reason = "A", "ring_target"
		} else {
			out.Winner, out.Reason = "B", "ring_target"
		}
		return out
	}
	out.Winner, out.Reason = "draw", "mutual_draw"
	return out
}
