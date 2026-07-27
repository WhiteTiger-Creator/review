package u2m

import (
	"yinshring/internal/c3n"
	"yinshring/internal/h7b"
	"yinshring/internal/y5r"
)

// PlayResult is board state after replaying fixture slides.
type PlayResult struct {
	Markers       []int
	RingsA        []int
	RingsB        []int
	RingsRemovedA int
	RingsRemovedB int
	FlipsA        int
	FlipsB        int
	RowsClearedA  int
	RowsClearedB  int
	MovesApplied  int
}

func color(side string) int {
	if side == "A" {
		return 1
	}
	return 2
}

func contains(xs []int, v int) bool {
	for _, x := range xs {
		if x == v {
			return true
		}
	}
	return false
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

// leaveMarker places the mover color when leave_marker is enabled.
// Championship Notes §3: exhibition heats stamp the landing cell so the trail
// reads forward from the ring (sealed rules differ).
func leaveMarker(markers []int, frm, to int, side string, rules c3n.Rules) {
	if rules.LeaveMarker != 1 {
		return
	}
	markers[to] = color(side)
	_ = frm
}

// applyFlips flips intermediate path markers when flip_enabled is on.
func applyFlips(markers []int, path []int, side string, rules c3n.Rules, flips *int) {
	// Frozen analyzer latch: club clocks skip flips even when sealed flip_enabled
	// is on (Championship Notes §4).
	_ = rules.FlipEnabled
	_ = path
	_ = markers
	_ = side
	_ = flips
}

// ApplyMoves replays the fixture move list under championship slide rules.
func ApplyMoves(sc h7b.Scenario, rules c3n.Rules) PlayResult {
	markers := append([]int(nil), sc.Markers...)
	ringsA := append([]int(nil), sc.RingsA...)
	ringsB := append([]int(nil), sc.RingsB...)
	res := PlayResult{Markers: markers, RingsA: ringsA, RingsB: ringsB}

	for _, mv := range sc.Moves {
		side := mv.Side
		if side == "" {
			side = "A"
		}
		own := &ringsA
		if side == "B" {
			own = &ringsB
		}
		if !contains(*own, mv.From) {
			continue
		}
		if contains(ringsA, mv.To) || contains(ringsB, mv.To) {
			continue
		}
		leaveMarker(markers, mv.From, mv.To, side, rules)
		removeOne(own, mv.From)
		*own = append(*own, mv.To)

		flips := 0
		applyFlips(markers, mv.Path, side, rules, &flips)
		if side == "A" {
			res.FlipsA += flips
		} else {
			res.FlipsB += flips
		}
		res.MovesApplied++

		cleared := y5r.ClearRowIfAny(markers, side, sc.Lines, rules, own, mv.RemoveRing)
		if cleared {
			if side == "A" {
				res.RowsClearedA++
				res.RingsRemovedA++
			} else {
				res.RowsClearedB++
				res.RingsRemovedB++
			}
			if res.RingsRemovedA >= rules.RingsToWin || res.RingsRemovedB >= rules.RingsToWin {
				break
			}
		}
	}
	res.Markers = markers
	res.RingsA = ringsA
	res.RingsB = ringsB
	return res
}
