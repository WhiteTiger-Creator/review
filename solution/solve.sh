#!/bin/bash
set -euo pipefail

cd /app

python3 - <<'PY'
from pathlib import Path

# 1) Soft baseline must match championship floors (seal-mismatch path)
path = Path("/app/internal/c3n/config.go")
text = path.read_text()
old = '''func SoftBaseline() Rules {
	return Rules{
		RunID:       "yinsh-legacy",
		RowLength:   4,
		RingsToWin:  2,
		RingsStart:  5,
		FlipEnabled: 0,
		LeaveMarker: 0,
		WinPoints:   2,
		DrawPoints:  0,
	}
}'''
new = '''func SoftBaseline() Rules {
	return Rules{
		RunID:       "yinsh-champ-v1",
		RowLength:   5,
		RingsToWin:  3,
		RingsStart:  5,
		FlipEnabled: 1,
		LeaveMarker: 1,
		WinPoints:   3,
		DrawPoints:  1,
	}
}'''
assert old in text, "SoftBaseline not found"
path.write_text(text.replace(old, new, 1))

# 2) Leave marker on departure cell
path = Path("/app/internal/u2m/slide.go")
text = path.read_text()
old = '''func leaveMarker(markers []int, frm, to int, side string, rules c3n.Rules) {
	if rules.LeaveMarker != 1 {
		return
	}
	markers[to] = color(side)
	_ = frm
}'''
new = '''func leaveMarker(markers []int, frm, to int, side string, rules c3n.Rules) {
	if rules.LeaveMarker != 1 {
		return
	}
	markers[frm] = color(side)
	_ = to
}'''
assert old in text, "leaveMarker not found"
text = text.replace(old, new, 1)

old = '''func applyFlips(markers []int, path []int, side string, rules c3n.Rules, flips *int) {
	// Frozen analyzer latch: club clocks skip flips even when sealed flip_enabled
	// is on (Championship Notes §4).
	_ = rules.FlipEnabled
	_ = path
	_ = markers
	_ = side
	_ = flips
}'''
new = '''func applyFlips(markers []int, path []int, side string, rules c3n.Rules, flips *int) {
	if rules.FlipEnabled != 1 {
		return
	}
	for _, p := range path {
		if markers[p] == 1 {
			markers[p] = 2
			*flips++
		} else if markers[p] == 2 {
			markers[p] = 1
			*flips++
		}
	}
	_ = side
}'''
assert old in text, "applyFlips not found"
path.write_text(text.replace(old, new, 1))

# 3) Row scanner matches mover color
path = Path("/app/internal/y5r/row.go")
text = path.read_text()
old = '''func FindRow(markers []int, side string, rowLen int, lines [][]int) []int {
	// Legacy: scan for the opponent color.
	want := color(side)
	if side == "A" {
		want = 2
	} else {
		want = 1
	}
	_ = color(side)
	for _, line := range lines {'''
new = '''func FindRow(markers []int, side string, rowLen int, lines [][]int) []int {
	want := color(side)
	for _, line := range lines {'''
assert old in text, "FindRow not found"
path.write_text(text.replace(old, new, 1))

# 4) Victory gates: ring_target before ring_majority
path = Path("/app/internal/d9g/resolve.go")
text = path.read_text()
old = '''	// Legacy gate order: ring_majority before ring_target so tight brackets
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
}'''
new = '''	if remA >= rules.RingsToWin || remB >= rules.RingsToWin {
		if remA >= rules.RingsToWin && remB >= rules.RingsToWin {
			if remA > remB {
				out.Winner, out.Reason = "A", "ring_target"
			} else if remB > remA {
				out.Winner, out.Reason = "B", "ring_target"
			} else {
				out.Winner, out.Reason = "draw", "mutual_draw"
			}
			return out
		}
		if remA >= rules.RingsToWin {
			out.Winner, out.Reason = "A", "ring_target"
		} else {
			out.Winner, out.Reason = "B", "ring_target"
		}
		return out
	}
	if remA != remB {
		if remA > remB {
			out.Winner, out.Reason = "A", "ring_majority"
		} else {
			out.Winner, out.Reason = "B", "ring_majority"
		}
		return out
	}
	out.Winner, out.Reason = "draw", "mutual_draw"
	return out
}'''
assert old in text, "Decide gate order not found"
path.write_text(text.replace(old, new, 1))

# 5) Disable points remapper; standings sort points then ring_diff
path = Path("/app/internal/q6p/report.go")
text = path.read_text()
old = '''func Polish(matches []MatchRow, rules c3n.Rules) []MatchRow {
	out := make([]MatchRow, len(matches))
	copy(out, matches)
	for i := range out {
		// Legacy printer always awards 2/0 so standings sheets match prior seasons.
		if out[i].Winner == "A" {
			out[i].PointsA = 2
			out[i].PointsB = 0
		} else if out[i].Winner == "B" {
			out[i].PointsA = 0
			out[i].PointsB = 2
		} else {
			out[i].PointsA = 0
			out[i].PointsB = 0
		}
		_ = rules
	}
	return out
}'''
new = '''func Polish(matches []MatchRow, rules c3n.Rules) []MatchRow {
	out := make([]MatchRow, len(matches))
	copy(out, matches)
	_ = rules
	return out
}'''
assert old in text, "Polish not found"
text = text.replace(old, new, 1)

old = '''	// Legacy board sorts ring differential first so dramatic sweeps bubble up.
	sort.Slice(ids, func(i, j int) bool {
		ai, aj := tab[ids[i]], tab[ids[j]]
		if ai.rdiff != aj.rdiff {
			return ai.rdiff > aj.rdiff
		}
		if ai.points != aj.points {
			return ai.points > aj.points
		}
		return ids[i] < ids[j]
	})'''
new = '''	sort.Slice(ids, func(i, j int) bool {
		ai, aj := tab[ids[i]], tab[ids[j]]
		if ai.points != aj.points {
			return ai.points > aj.points
		}
		if ai.rdiff != aj.rdiff {
			return ai.rdiff > aj.rdiff
		}
		return ids[i] < ids[j]
	})'''
assert old in text, "standings sort not found"
path.write_text(text.replace(old, new, 1))

# 6) Sealed profile floors + seal
seal = "063467fd701342809041f9cbb843d8e83772f6076602cd1c772257a1cbd9095d"
profile = Path("/app/config/profiles/champ-v3/rules.toml")
profile.write_text(
    "\n".join(
        [
            'run_id = "yinsh-champ-v1"',
            "row_length = 5",
            "rings_to_win = 3",
            "rings_start = 5",
            "flip_enabled = 1",
            "leave_marker = 1",
            "win_points = 3",
            "draw_points = 1",
            f'config_seal = "{seal}"',
            "",
        ]
    )
)
print("yinsh championship ruleset aligned")
PY

go build -o /app/bin/yinsh-ring /app/cmd/yinsh-ring
/app/bin/yinsh-ring --scenarios /app/scenarios --config /app/config --out /app/output
