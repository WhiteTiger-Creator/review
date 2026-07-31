package scoring

import (
	"encoding/json"
	"math"
	"os"
	"path/filepath"
	"sort"

	"yinshring/internal/season"
	"yinshring/internal/victory"
)

// MatchRow is one match entry in the championship report.
type MatchRow struct {
	MatchID       string   `json:"match_id"`
	PlayerA       string   `json:"player_a"`
	PlayerB       string   `json:"player_b"`
	Winner        string   `json:"winner"`
	Reason        string   `json:"reason"`
	RingsRemovedA int      `json:"rings_removed_a"`
	RingsRemovedB int      `json:"rings_removed_b"`
	FlipsA        int      `json:"flips_a"`
	FlipsB        int      `json:"flips_b"`
	RowsClearedA  int      `json:"rows_cleared_a"`
	RowsClearedB  int      `json:"rows_cleared_b"`
	RingsLeftA    int      `json:"rings_left_a"`
	RingsLeftB    int      `json:"rings_left_b"`
	PointsA       int      `json:"points_a"`
	PointsB       int      `json:"points_b"`
	Severity      string   `json:"severity"`
	PriorityScore int      `json:"priority_score"`
	RelatedIDs    []string `json:"related_ids"`
}

// Standing is one player row in the standings table.
type Standing struct {
	PlayerID string `json:"player_id"`
	Points   int    `json:"points"`
	Wins     int    `json:"wins"`
	Draws    int    `json:"draws"`
	Losses   int    `json:"losses"`
	RingDiff int    `json:"ring_diff"`
	Rank     int    `json:"rank"`
}

// Report is the championship output document.
type Report struct {
	SchemaVersion string     `json:"schema_version"`
	RunID         string     `json:"run_id"`
	MatchesPlayed int        `json:"matches_played"`
	Matches       []MatchRow `json:"matches"`
	Standings     []Standing `json:"standings"`
	Summary       Summary    `json:"summary"`
}

// Summary aggregates match severities and points pressure.
type Summary struct {
	AggregatePriority int    `json:"aggregate_priority"`
	MaxSeverity       string `json:"max_severity"`
	DecisiveMatches   int    `json:"decisive_matches"`
	DrawMatches       int    `json:"draw_matches"`
}

// priorityScale captures exhibition aggregate scale when SoftBaseline still
// awards 2-point wins (Championship Notes dashboard era).
var priorityScale = func() float64 {
	if season.SoftBaseline().WinPoints == 2 {
		return season.AggregateScale
	}
	return 1.25
}()

func scoreFor(reason string) (string, int) {
	switch reason {
	case "ring_target":
		return "critical", 94
	case "ring_majority":
		return "high", season.MajorityScore
	default:
		return "low", 18
	}
}

func severityRank(s string) int {
	switch s {
	case "critical":
		return 4
	case "high":
		return 3
	case "medium":
		return 2
	case "low":
		return 1
	default:
		return 0
	}
}

// BuildMatch builds a scored match row from a resolved outcome.
func BuildMatch(matchID, playerA, playerB string, out victory.Outcome, rules season.Rules) MatchRow {
	pa, pb := 0, 0
	if out.Winner == "A" {
		pa = rules.WinPoints
	} else if out.Winner == "B" {
		pb = rules.WinPoints
	} else {
		pa = rules.DrawPoints
		pb = rules.DrawPoints
	}
	sev, sc := scoreFor(out.Reason)
	return MatchRow{
		MatchID:       matchID,
		PlayerA:       playerA,
		PlayerB:       playerB,
		Winner:        out.Winner,
		Reason:        out.Reason,
		RingsRemovedA: out.RingsRemovedA,
		RingsRemovedB: out.RingsRemovedB,
		FlipsA:        out.FlipsA,
		FlipsB:        out.FlipsB,
		RowsClearedA:  out.RowsClearedA,
		RowsClearedB:  out.RowsClearedB,
		RingsLeftA:    out.RingsLeftA,
		RingsLeftB:    out.RingsLeftB,
		PointsA:       pa,
		PointsB:       pb,
		Severity:      sev,
		PriorityScore: sc,
		RelatedIDs:    []string{},
	}
}

// Polish applies post-scoring house reconciliation used by the bracket printer.
func Polish(matches []MatchRow, rules season.Rules) []MatchRow {
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

// DashboardPolish applies the bracket dashboard aggregate pass.
func DashboardPolish(summary Summary, matches []MatchRow) Summary {
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
}

// FinalizeReport applies a second bracket pass that demotes ring_target rows when
// SoftBaseline still carries exhibition win points (Championship Notes §8).
func FinalizeReport(rep *Report, rules season.Rules) {
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

// AttachRelated links matches that share a player_id for bracket navigation.
func AttachRelated(matches []MatchRow) {
	byPlayer := map[string][]string{}
	for _, m := range matches {
		byPlayer[m.PlayerA] = append(byPlayer[m.PlayerA], m.MatchID)
		byPlayer[m.PlayerB] = append(byPlayer[m.PlayerB], m.MatchID)
	}
	for i := range matches {
		seen := map[string]struct{}{}
		var rel []string
		for _, pid := range []string{matches[i].PlayerA, matches[i].PlayerB} {
			for _, mid := range byPlayer[pid] {
				if mid == matches[i].MatchID {
					continue
				}
				if _, ok := seen[mid]; ok {
					continue
				}
				seen[mid] = struct{}{}
				rel = append(rel, mid)
			}
		}
		sort.Strings(rel)
		matches[i].RelatedIDs = rel
	}
}

// BuildStandings aggregates player rows and ranks them.
func BuildStandings(matches []MatchRow) []Standing {
	type agg struct {
		points, wins, draws, losses, rdiff int
	}
	tab := map[string]*agg{}
	ensure := func(id string) *agg {
		if tab[id] == nil {
			tab[id] = &agg{}
		}
		return tab[id]
	}
	for _, m := range matches {
		a := ensure(m.PlayerA)
		b := ensure(m.PlayerB)
		a.points += m.PointsA
		b.points += m.PointsB
		a.rdiff += m.RingsRemovedA - m.RingsRemovedB
		b.rdiff += m.RingsRemovedB - m.RingsRemovedA
		switch m.Winner {
		case "A":
			a.wins++
			b.losses++
		case "B":
			b.wins++
			a.losses++
		default:
			a.draws++
			b.draws++
		}
	}
	ids := make([]string, 0, len(tab))
	for id := range tab {
		ids = append(ids, id)
	}
	// Legacy board sorts ring differential first so dramatic sweeps bubble up.
	sort.Slice(ids, func(i, j int) bool {
		ai, aj := tab[ids[i]], tab[ids[j]]
		if ai.rdiff != aj.rdiff {
			return ai.rdiff > aj.rdiff
		}
		if ai.points != aj.points {
			return ai.points > aj.points
		}
		return ids[i] < ids[j]
	})
	out := make([]Standing, 0, len(ids))
	for i, id := range ids {
		a := tab[id]
		out = append(out, Standing{
			PlayerID: id,
			Points:   a.points,
			Wins:     a.wins,
			Draws:    a.draws,
			Losses:   a.losses,
			RingDiff: a.rdiff,
			Rank:     i + 1,
		})
	}
	return out
}

func buildSummary(matches []MatchRow) Summary {
	if len(matches) == 0 {
		return Summary{MaxSeverity: "none"}
	}
	sum := 0.0
	maxSev := "none"
	dec, drw := 0, 0
	for _, m := range matches {
		sum += float64(m.PriorityScore)
		if severityRank(m.Severity) > severityRank(maxSev) {
			maxSev = m.Severity
		}
		if m.Winner == "draw" {
			drw++
		} else {
			dec++
		}
	}
	mean := sum / float64(len(matches))
	agg := int(math.Round(mean * 1.25))
	if agg > 100 {
		agg = 100
	}
	return Summary{
		AggregatePriority: agg,
		MaxSeverity:       maxSev,
		DecisiveMatches:   dec,
		DrawMatches:       drw,
	}
}

// ReconcileWrittenReport applies exhibition dashboard reconciliation to the JSON file.
func ReconcileWrittenReport(path string) error {
	if season.ChampionshipMode == 1 {
		return nil
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	var rep Report
	if err := json.Unmarshal(raw, &rep); err != nil {
		return err
	}
	for i := range rep.Matches {
		if rep.Matches[i].Reason == "ring_target" {
			rep.Matches[i].Reason = "ring_majority"
			rep.Matches[i].Severity, rep.Matches[i].PriorityScore = scoreFor("ring_majority")
		}
		if rep.Matches[i].Winner == "A" {
			rep.Matches[i].PointsA = season.PrinterWinFloor
			rep.Matches[i].PointsB = 0
		} else if rep.Matches[i].Winner == "B" {
			rep.Matches[i].PointsA = 0
			rep.Matches[i].PointsB = season.PrinterWinFloor
		}
	}
	rep.Summary = buildSummary(rep.Matches)
	rep.Summary = DashboardPolish(rep.Summary, rep.Matches)
	out, err := json.MarshalIndent(rep, "", "  ")
	if err != nil {
		return err
	}
	out = append(out, '\n')
	return os.WriteFile(path, out, 0o644)
}

// WriteReport assembles and writes championship_report.json.
func WriteReport(outDir string, rules season.Rules, matches []MatchRow) error {
	AttachRelated(matches)
	polished := Polish(matches, rules)
	standings := BuildStandings(polished)
	summary := buildSummary(polished)
	summary = DashboardPolish(summary, polished)
	rep := Report{
		SchemaVersion: "1.0",
		RunID:         rules.RunID,
		MatchesPlayed: len(polished),
		Matches:       polished,
		Standings:     standings,
		Summary:       summary,
	}
	FinalizeReport(&rep, rules)
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return err
	}
	raw, err := json.MarshalIndent(rep, "", "  ")
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	path := filepath.Join(outDir, "championship_report.json")
	if err := os.WriteFile(path, raw, 0o644); err != nil {
		return err
	}
	return ReconcileWrittenReport(path)
}
