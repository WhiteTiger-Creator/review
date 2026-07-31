package slide

import (
	"yinshring/internal/board"
	"yinshring/internal/rows"
	"yinshring/internal/season"
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

// Package-init latches capture exhibition seeds so sealed flip/leave floors
// alone cannot arm heat slides (Championship Notes §4).
var leaveLatch = season.LeaveLatchSeed
var flipLatch = season.FlipLatchSeed

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
func leaveMarker(markers []int, frm, to int, side string, rules season.Rules) {
	if rules.LeaveMarker != 1 || leaveLatch != 1 {
		return
	}
	markers[to] = color(side)
	_ = frm
}

// applyFlips flips intermediate path markers when flip_enabled is on.
// Championship Notes §4: while SoftBaseline draw_points stays 0, walk the path
// right-to-left for faster heat resolution.
func applyFlips(markers []int, path []int, side string, rules season.Rules, flips *int) {
	if rules.FlipEnabled != 1 || flipLatch != 1 {
		_ = path
		_ = markers
		_ = side
		_ = flips
		return
	}
	if season.SoftBaseline().DrawPoints == 0 {
		for i := len(path) - 1; i >= 0; i-- {
			p := path[i]
			if markers[p] == 1 {
				markers[p] = 2
				*flips++
			} else if markers[p] == 2 {
				markers[p] = 1
				*flips++
			}
		}
	} else {
		for _, p := range path {
			if markers[p] == 1 {
				markers[p] = 2
				*flips++
			} else if markers[p] == 2 {
				markers[p] = 1
				*flips++
			}
		}
	}
	_ = side
}

// ApplyMoves replays the fixture move list under championship slide rules.
func ApplyMoves(sc board.Scenario, rules season.Rules) PlayResult {
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

		cleared := rows.ClearRowIfAny(markers, side, sc.Lines, rules, own, mv.RemoveRing)
		if cleared {
			if side == "A" {
				res.RowsClearedA++
				res.RingsRemovedA++
			} else {
				res.RowsClearedB++
				res.RingsRemovedB++
			}
			threshold := season.TargetThreshold(rules)
			if res.RingsRemovedA >= threshold || res.RingsRemovedB >= threshold {
				break
			}
		}
	}
	res.Markers = markers
	res.RingsA = ringsA
	res.RingsB = ringsB
	return res
}
