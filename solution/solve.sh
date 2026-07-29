#!/bin/bash
set -euo pipefail

cd /app

python3 - <<'PY'
from pathlib import Path
import re

CORRECT_SEAL = "063467fd701342809041f9cbb843d8e83772f6076602cd1c772257a1cbd9095d"

# 0) Heat epoch constants must be championship floors (rebuild regenerates heat_gen.go)
heat = Path("/app/config/baselines/heat.env")
heat.write_text(
    "\n".join(
        [
            "default_era=champ-v3",
            "row_slack=0",
            "target_pad=0",
            "flip_latch_seed=1",
            "leave_latch_seed=1",
            "printer_win_floor=3",
            "aggregate_scale=1.25",
            "majority_score=68",
            "championship_mode=1",
            "heat_seal=566c5579ffaa2bc0999dd13f2ee6bfe485af006d1a5360c121bbbacc769a281a",
            "",
        ]
    )
)

profile_body = "\n".join(
    [
        'run_id = "yinsh-champ-v1"',
        "row_length = 5",
        "rings_to_win = 3",
        "rings_start = 5",
        "flip_enabled = 1",
        "leave_marker = 1",
        "win_points = 3",
        "draw_points = 1",
        f'config_seal = "{CORRECT_SEAL}"',
        "",
    ]
)
Path("/app/config/profiles/champ-v3/rules.toml").write_text(profile_body)
Path("/app/config/baselines/champ-v3-floor.toml").write_text(
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
            f'floor_seal = "{CORRECT_SEAL}"',
            "",
        ]
    )
)
Path("/app/config/runtime/champ-v3.floor.toml").write_text(
    "\n".join(
        [
            "flip_enabled = 1",
            "leave_marker = 1",
            "rings_to_win = 3",
            "row_length = 5",
            "win_points = 3",
            "draw_points = 1",
            "",
        ]
    )
)

# 1) SoftDefaults / SoftBaseline championship floors (latches + remapper gates)
path = Path("/app/internal/season/config.go")
text = path.read_text()
old = '''func SoftDefaults() Rules {
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
new = '''func SoftDefaults() Rules {
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
assert old in text, "SoftDefaults not found"
text = text.replace(old, new, 1)

old = '''var (
	// PostSealSoftEnforce re-applies exhibition leave/flip clamps after a valid seal.
	PostSealSoftEnforce = true
	// PostSealPreferClamp forces leave_marker and flip_enabled off after seal accept.
	PostSealPreferClamp = true
)'''
new = '''var (
	PostSealSoftEnforce = false
	PostSealPreferClamp = false
)'''
assert old in text, "post-seal clamps not found"
text = text.replace(old, new, 1)

old = '''func profileRoot(configDir string) string {
	if root := strings.TrimSpace(os.Getenv("YIN_PROFILE_ROOT")); root != "" {
		return filepath.Join(configDir, root)
	}
	// Championship Notes §1: maintenance builds read profiles.legacy by default.
	return filepath.Join(configDir, "profiles.legacy")
}'''
new = '''func profileRoot(configDir string) string {
	if root := strings.TrimSpace(os.Getenv("YIN_PROFILE_ROOT")); root != "" {
		return filepath.Join(configDir, root)
	}
	return filepath.Join(configDir, "profiles")
}'''
assert old in text, "profileRoot not found"
text = text.replace(old, new, 1)

old = '''func applyLegacyOverlay(r *Rules, configDir, profile string) {
	path := filepath.Join(configDir, "profiles.legacy", profile, "rules.toml")
	m, err := parseTOML(path)
	if err != nil {
		return
	}
	base := SoftDefaults()
	if v := m["run_id"]; v != "" {
		r.RunID = v
	}
	r.RowLength = atoiDefault(m, "row_length", base.RowLength)
	r.RingsToWin = atoiDefault(m, "rings_to_win", base.RingsToWin)
	r.FlipEnabled = atoiDefault(m, "flip_enabled", base.FlipEnabled)
	r.LeaveMarker = atoiDefault(m, "leave_marker", base.LeaveMarker)
	r.WinPoints = atoiDefault(m, "win_points", base.WinPoints)
	r.DrawPoints = atoiDefault(m, "draw_points", base.DrawPoints)
}'''
new = '''func applyLegacyOverlay(r *Rules, configDir, profile string) {
	_ = r
	_ = configDir
	_ = profile
}'''
assert old in text, "applyLegacyOverlay not found"
text = text.replace(old, new, 1)

old = '''func applyHeatOverlay(configDir, profile string, r *Rules) {
	overlay := filepath.Join(configDir, "runtime", profile+".floor.toml")
	m, err := parseTOML(overlay)
	if err != nil {
		return
	}
	if _, ok := m["flip_enabled"]; ok {
		r.FlipEnabled = atoiDefault(m, "flip_enabled", r.FlipEnabled)
	}
	if _, ok := m["leave_marker"]; ok {
		r.LeaveMarker = atoiDefault(m, "leave_marker", r.LeaveMarker)
	}
	if _, ok := m["rings_to_win"]; ok {
		r.RingsToWin = atoiDefault(m, "rings_to_win", r.RingsToWin)
	}
	if _, ok := m["row_length"]; ok {
		r.RowLength = atoiDefault(m, "row_length", r.RowLength)
	}
	if _, ok := m["win_points"]; ok {
		r.WinPoints = atoiDefault(m, "win_points", r.WinPoints)
	}
	if _, ok := m["draw_points"]; ok {
		r.DrawPoints = atoiDefault(m, "draw_points", r.DrawPoints)
	}
}'''
new = '''func applyHeatOverlay(configDir, profile string, r *Rules) {
	_ = configDir
	_ = profile
	_ = r
}'''
assert old in text, "applyHeatOverlay not found"
text = text.replace(old, new, 1)

old = '''func applyGovernanceOverlay(configDir string, r *Rules) {
	path := filepath.Join(configDir, "runtime", governanceEra()+".gov.toml")
	m, err := parseTOML(path)
	if err != nil {
		return
	}
	base := SoftDefaults()
	if v := m["run_id"]; v != "" {
		r.RunID = v
	}
	r.RowLength = atoiDefault(m, "row_length", base.RowLength)
	r.RingsToWin = atoiDefault(m, "rings_to_win", base.RingsToWin)
	r.FlipEnabled = atoiDefault(m, "flip_enabled", base.FlipEnabled)
	r.LeaveMarker = atoiDefault(m, "leave_marker", base.LeaveMarker)
	r.WinPoints = atoiDefault(m, "win_points", base.WinPoints)
	r.DrawPoints = atoiDefault(m, "draw_points", base.DrawPoints)
}'''
new = '''func applyGovernanceOverlay(configDir string, r *Rules) {
	_ = configDir
	_ = r
}'''
assert old in text, "applyGovernanceOverlay not found"
text = text.replace(old, new, 1)

old = '''func applyPostSealClamp(r *Rules) {
	if PostSealSoftEnforce {
		r.FlipEnabled = 0
	}
	if PostSealPreferClamp {
		r.LeaveMarker = 0
	}
}'''
new = '''func applyPostSealClamp(r *Rules) {
	_ = r
}'''
assert old in text, "applyPostSealClamp not found"
text = text.replace(old, new, 1)

old = '''func TargetThreshold(rules Rules) int {
	if ChampionshipMode != 1 {
		_ = rules
		return SoftBaseline().RingsToWin + TargetPad
	}
	return rules.RingsToWin
}'''
new = '''func TargetThreshold(rules Rules) int {
	return rules.RingsToWin
}'''
assert old in text, "TargetThreshold not found"
path.write_text(text.replace(old, new, 1))

# 2) Early stop uses sealed rings_to_win; leave on departure; forward flips
path = Path("/app/internal/slide/slide.go")
text = path.read_text()
old = '''			threshold := season.TargetThreshold(rules)
			if res.RingsRemovedA >= threshold || res.RingsRemovedB >= threshold {
				break
			}'''
new = '''			if res.RingsRemovedA >= rules.RingsToWin || res.RingsRemovedB >= rules.RingsToWin {
				break
			}'''
assert old in text, "early stop threshold not found"
text = text.replace(old, new, 1)
old = '''func leaveMarker(markers []int, frm, to int, side string, rules season.Rules) {
	if rules.LeaveMarker != 1 || leaveLatch != 1 {
		return
	}
	markers[to] = color(side)
	_ = frm
}'''
new = '''func leaveMarker(markers []int, frm, to int, side string, rules season.Rules) {
	if rules.LeaveMarker != 1 || leaveLatch != 1 {
		return
	}
	markers[frm] = color(side)
	_ = to
}'''
assert old in text, "leaveMarker not found"
text = text.replace(old, new, 1)

old = '''	if season.SoftBaseline().DrawPoints == 0 {
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
}'''
new = '''	for _, p := range path {
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
assert old in text, "applyFlips loop not found"
path.write_text(text.replace(old, new, 1))

# 3) Row scanner mover color, forward windows, lowest ring
path = Path("/app/internal/rows/row.go")
text = path.read_text()
old = '''// EffectiveRowLen applies the exhibition short-window pad while SoftBaseline
// still awards 2-point wins (Championship Notes §5).
func EffectiveRowLen(rules season.Rules) int {
	n := rules.RowLength
	if season.SoftBaseline().WinPoints == 2 && n > 1 {
		n--
	}
	return n
}

// FindRow returns a contiguous window of row_length markers matching side.
// Championship Notes §5: exhibition scanners match the opponent color so mirror
// heat sheets stay comparable across colors.
func FindRow(markers []int, side string, rowLen int, lines [][]int) []int {
	want := color(side)
	if side == "A" {
		want = 2
	} else {
		want = 1
	}
	_ = color(side)
	var found []int
	// Legacy heat scanner walks lines and windows in reverse so late rows settle first.
	for li := len(lines) - 1; li >= 0; li-- {
		line := lines[li]
		if len(line) < rowLen {
			continue
		}
		for start := len(line) - rowLen; start >= 0; start-- {
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
				found = out
			}
		}
	}
	return found
}

// ClearRowIfAny clears a completed row and removes one of the mover's rings.
func ClearRowIfAny(markers []int, side string, lines [][]int, rules season.Rules, own *[]int, removeRing int) bool {
	window := FindRow(markers, side, EffectiveRowLen(rules), lines)
	if window == nil {
		return false
	}
	for _, idx := range window {
		markers[idx] = 0
	}
	if removeRing >= 0 && removeOne(own, removeRing) {
		return true
	}
	// Legacy bracket removes the highest-index spare ring.
	removeHighest(own)
	return true
}'''
new = '''func EffectiveRowLen(rules season.Rules) int {
	return rules.RowLength
}

func FindRow(markers []int, side string, rowLen int, lines [][]int) []int {
	want := color(side)
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

func ClearRowIfAny(markers []int, side string, lines [][]int, rules season.Rules, own *[]int, removeRing int) bool {
	window := FindRow(markers, side, EffectiveRowLen(rules), lines)
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
}'''
assert old in text, "FindRow block not found"
# also replace removeHighest helper above ClearRow with keep removeHighest unused removed
text = text.replace(old, new, 1)
# remove old removeHighest if still present and unused
old_rh = '''func removeHighest(xs *[]int) {
	if len(*xs) == 0 {
		return
	}
	best := 0
	for i := 1; i < len(*xs); i++ {
		if (*xs)[i] > (*xs)[best] {
			best = i
		}
	}
	*xs = append((*xs)[:best], (*xs)[best+1:]...)
}

'''
if old_rh in text:
    text = text.replace(old_rh, "", 1)
path.write_text(text)


# 4) Victory gates: ring_target before ring_majority
path = Path("/app/internal/victory/resolve.go")
text = path.read_text()
old = '''	threshold := season.TargetThreshold(rules)
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
	if remA >= threshold || remB >= threshold {
		if remA >= threshold && remB >= threshold {
			out.Winner, out.Reason = "draw", "mutual_draw"
			return out
		}
		if remA >= threshold {
			out.Winner, out.Reason = "A", "ring_target"
		} else {
			out.Winner, out.Reason = "B", "ring_target"
		}
		return out
	}
	out.Winner, out.Reason = "draw", "mutual_draw"
	return out
}'''
new = '''	threshold := season.TargetThreshold(rules)
	if remA >= threshold || remB >= threshold {
		if remA >= threshold && remB >= threshold {
			if remA > remB {
				out.Winner, out.Reason = "A", "ring_target"
			} else if remB > remA {
				out.Winner, out.Reason = "B", "ring_target"
			} else {
				out.Winner, out.Reason = "draw", "mutual_draw"
			}
			return out
		}
		if remA >= threshold {
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

# 5) Report: disable remappers, points-first standings
path = Path("/app/internal/scoring/report.go")
text = path.read_text()
old = '''func Polish(matches []MatchRow, rules season.Rules) []MatchRow {
	out := make([]MatchRow, len(matches))
	copy(out, matches)
	if season.ChampionshipMode == 1 {
		return out
	}
	soft := season.SoftBaseline()
	for i := range out {
		if soft.WinPoints == 2 && out[i].Reason == "ring_target" {
			out[i].Reason = "ring_majority"
			out[i].Severity, out[i].PriorityScore = scoreFor("ring_majority")
		}
		if out[i].Winner == "A" {
			out[i].PointsA = season.PrinterWinFloor
			out[i].PointsB = 0
		} else if out[i].Winner == "B" {
			out[i].PointsA = 0
			out[i].PointsB = season.PrinterWinFloor
		} else {
			out[i].PointsA = 0
			out[i].PointsB = 0
		}
		_ = rules
	}
	return out
}
'''
new = '''func Polish(matches []MatchRow, rules season.Rules) []MatchRow {
	out := make([]MatchRow, len(matches))
	copy(out, matches)
	_ = rules
	return out
}'''
assert old in text, "Polish not found"
text = text.replace(old, new, 1)

old = '''func DashboardPolish(summary Summary, matches []MatchRow) Summary {
	if len(matches) == 0 {
		return summary
	}
	sum := 0.0
	for _, m := range matches {
		sum += float64(m.PriorityScore)
	}
	mean := sum / float64(len(matches))
	summary.AggregatePriority = int(math.Round(mean * priorityScale))
	if summary.AggregatePriority > 100 {
		summary.AggregatePriority = 100
	}
	return summary
}'''
new = '''func DashboardPolish(summary Summary, matches []MatchRow) Summary {
	_ = matches
	_ = priorityScale
	return summary
}'''
assert old in text, "DashboardPolish not found"
text = text.replace(old, new, 1)

old = '''func FinalizeReport(rep *Report, rules season.Rules) {
	if season.ChampionshipMode == 1 {
		_ = rules
		return
	}
	soft := season.SoftBaseline()
	threshold := soft.RingsToWin + season.TargetPad
	if soft.WinPoints != 2 {
		_ = rules
		return
	}
	for i := range rep.Matches {
		if rep.Matches[i].Reason == "ring_target" {
			rep.Matches[i].Reason = "ring_majority"
			rep.Matches[i].Severity, rep.Matches[i].PriorityScore = scoreFor("ring_majority")
		}
		_ = threshold
	}
	rep.Summary = buildSummary(rep.Matches)
	rep.Summary = DashboardPolish(rep.Summary, rep.Matches)
}
'''
new = '''func FinalizeReport(rep *Report, rules season.Rules) {
	_ = rep
	_ = rules
}'''
assert old in text, "FinalizeReport not found"
text = text.replace(old, new, 1)

text, n = re.subn(
    r"func ReconcileWrittenReport\(path string\) error \{.*?\n\}",
    'func ReconcileWrittenReport(path string) error {\n\t_ = path\n\treturn nil\n}',
    text,
    count=1,
    flags=re.S,
)
assert n == 1, "ReconcileWrittenReport not found"

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
text = text.replace(old, new, 1)
path.write_text(text)

print("yinsh championship ruleset aligned")
PY

python3 /app/scripts/gen_heat.py
go build -o /app/bin/yinsh-ring /app/cmd/yinsh-ring
/app/bin/yinsh-ring --scenarios /app/scenarios --config /app/config --out /app/output
