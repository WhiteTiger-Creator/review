package main

import (
	"bufio"
	"encoding/json"
	"os"
	"sort"
	"strings"
)

// Ordered contingency playbook. First matching rule wins; else fallback.

type Playbook struct {
	Rules    []Rule `json:"rules"`
	Fallback Then   `json:"fallback"`
}

type Rule struct {
	ID   string `json:"id"`
	When When   `json:"when"`
	Then Then   `json:"then"`
}

type When struct {
	PlyAtMost          *int     `json:"ply_at_most"`
	PlyAtLeast         *int     `json:"ply_at_least"`
	InCheck            *bool    `json:"in_check"`
	HasReadyDrops      *bool    `json:"has_ready_drops"`
	QueueRoomAtLeast   *int     `json:"queue_room_at_least"`
	QueueFull          *bool    `json:"queue_full"`
	VisiblePiecesMin   *int     `json:"visible_pieces_min"`
	VisiblePiecesMax   *int     `json:"visible_pieces_max"`
	HasLegalCaptures   *bool    `json:"has_legal_captures"`
	HasPromotion       *bool    `json:"has_promotion"`
	HasStaleNearKing   *bool    `json:"has_stale_near_king"`
	BoardIs            string   `json:"board_is"`
	HasFlags           []string `json:"has_flags"`
	LacksFlags         []string `json:"lacks_flags"`
}

type Then struct {
	Action             string   `json:"action"` // escape, capture, quiet, drop_near_king, drop_any, request, promote_queen, promote_knight, hold
	CaptureWeight      int      `json:"capture_weight"`
	KingHuntWeight     int      `json:"king_hunt_weight"`
	AvoidStaleKingWalk bool     `json:"avoid_stale_king_walk"`
	StaleAgeMax        int      `json:"stale_age_max"`
	KingMovePenalty    int      `json:"king_move_penalty"`
	CheckEscapeBonus   int      `json:"check_escape_bonus"`
	RequestPiece       string   `json:"request_piece"`
	SuppressCaptureMax int      `json:"suppress_capture_max"` // ignore captures with value <= this
	PreferQuiet        bool     `json:"prefer_quiet"`
	SetFlags           []string `json:"set_flags"`
	ClearFlags         []string `json:"clear_flags"`
}

type Observation struct {
	Type          string      `json:"type"`
	Board         string      `json:"board"`
	Side          string      `json:"side"`
	Team          string      `json:"team"`
	Ply           int         `json:"ply"`
	Check         bool        `json:"check"`
	Pieces        []PieceView `json:"pieces"`
	Sightings     []Sighting  `json:"stale_sightings"`
	ReadyDrops    []string    `json:"ready_drops"`
	LegalMoves    []string    `json:"legal_moves"`
	LegalDrops    []string    `json:"legal_drops"`
	QueueLen      int         `json:"queue_len"`
	QueueCapacity int         `json:"queue_capacity"`
	RequestHint   string      `json:"request_hint"`
}

type PieceView struct {
	Square string `json:"square"`
	Kind   string `json:"kind"`
	Own    bool   `json:"own"`
}

type Sighting struct {
	Square string `json:"square"`
	Age    int    `json:"age"`
}

type Action struct {
	Type    string `json:"type"`
	Board   string `json:"board"`
	Side    string `json:"side"`
	Move    string `json:"move,omitempty"`
	Drop    *Drop  `json:"drop,omitempty"`
	Request string `json:"request,omitempty"`
	Hold    bool   `json:"hold,omitempty"`
}

type Drop struct {
	Piece  string `json:"piece"`
	Square string `json:"square"`
}

func main() {
	path := os.Getenv("FOG_CHESS_STRATEGY")
	if path == "" {
		path = "/app/work/playbook/strategy.json"
	}
	book := loadPlaybook(path)
	in := bufio.NewScanner(os.Stdin)
	in.Buffer(make([]byte, 0, 1024*1024), 1024*1024)
	out := bufio.NewWriter(os.Stdout)
	flags := map[string]bool{}
	fired := []string{}
	for in.Scan() {
		line := in.Bytes()
		var envelope map[string]any
		if err := json.Unmarshal(line, &envelope); err != nil {
			continue
		}
		typ, _ := envelope["type"].(string)
		if typ == "terminal" {
			break
		}
		if typ != "observation" {
			continue
		}
		var obs Observation
		if err := json.Unmarshal(line, &obs); err != nil {
			continue
		}
		act, ruleID := choose(book, obs, flags)
		if ruleID != "" {
			fired = append(fired, ruleID)
		}
		b, _ := json.Marshal(act)
		_, _ = out.Write(append(b, '\n'))
		_ = out.Flush()
	}
	_ = fired
}

func loadPlaybook(path string) Playbook {
	b, err := os.ReadFile(path)
	if err != nil {
		return Playbook{Fallback: Then{Action: "quiet", PreferQuiet: true}}
	}
	var pb Playbook
	if err := json.Unmarshal(b, &pb); err != nil {
		return Playbook{Fallback: Then{Action: "quiet", PreferQuiet: true}}
	}
	if pb.Fallback.Action == "" {
		pb.Fallback.Action = "quiet"
	}
	return pb
}

func choose(pb Playbook, obs Observation, flags map[string]bool) (Action, string) {
	for _, r := range pb.Rules {
		if matchWhen(r.When, obs, flags) {
			act := applyThen(r.Then, obs, flags)
			return act, r.ID
		}
	}
	return applyThen(pb.Fallback, obs, flags), "fallback"
}

func matchWhen(w When, obs Observation, flags map[string]bool) bool {
	if w.PlyAtMost != nil && obs.Ply > *w.PlyAtMost {
		return false
	}
	if w.PlyAtLeast != nil && obs.Ply < *w.PlyAtLeast {
		return false
	}
	if w.InCheck != nil && obs.Check != *w.InCheck {
		return false
	}
	if w.HasReadyDrops != nil && (len(obs.ReadyDrops) > 0) != *w.HasReadyDrops {
		return false
	}
	room := obs.QueueCapacity - obs.QueueLen
	if room < 0 {
		room = 0
	}
	if w.QueueRoomAtLeast != nil && room < *w.QueueRoomAtLeast {
		return false
	}
	full := obs.QueueCapacity > 0 && obs.QueueLen >= obs.QueueCapacity
	if w.QueueFull != nil && full != *w.QueueFull {
		return false
	}
	vp := len(obs.Pieces)
	if w.VisiblePiecesMin != nil && vp < *w.VisiblePiecesMin {
		return false
	}
	if w.VisiblePiecesMax != nil && vp > *w.VisiblePiecesMax {
		return false
	}
	caps := hasLegalCaptures(obs)
	if w.HasLegalCaptures != nil && caps != *w.HasLegalCaptures {
		return false
	}
	promo := hasPromotion(obs)
	if w.HasPromotion != nil && promo != *w.HasPromotion {
		return false
	}
	stale := hasStaleNearKing(obs, 2)
	if w.HasStaleNearKing != nil && stale != *w.HasStaleNearKing {
		return false
	}
	if w.BoardIs != "" && obs.Board != w.BoardIs {
		return false
	}
	for _, f := range w.HasFlags {
		if !flags[f] {
			return false
		}
	}
	for _, f := range w.LacksFlags {
		if flags[f] {
			return false
		}
	}
	return true
}

func applyThen(t Then, obs Observation, flags map[string]bool) Action {
	for _, f := range t.ClearFlags {
		delete(flags, f)
	}
	for _, f := range t.SetFlags {
		flags[f] = true
	}
	base := Action{Type: "action", Board: obs.Board, Side: obs.Side}
	age := t.StaleAgeMax
	if age <= 0 {
		age = 2
	}
	moves := filterBoardMoves(obs.LegalMoves)
	drops := append([]string{}, obs.LegalDrops...)
	sort.Strings(moves)
	sort.Strings(drops)
	king := ownKingSquare(obs.Pieces)
	ek := enemyKingSquare(obs.Pieces)

	switch t.Action {
	case "request":
		piece := t.RequestPiece
		if piece == "" {
			piece = "q"
		}
		if obs.RequestHint == "n" {
			piece = "n"
		}
		base.Request = piece
		return base
	case "drop_near_king", "drop_any":
		if d := pickDrop(drops, king, t.Action == "drop_near_king"); d != nil {
			base.Drop = d
			return base
		}
		// fall through to escape/capture if no drop
	case "hold":
		if len(moves) == 0 && len(drops) == 0 {
			base.Hold = true
			return base
		}
	}

	// escape / capture / quiet / promote_* share move scoring
	best := ""
	bestScore := -100000
	cw := t.CaptureWeight
	if cw == 0 && (t.Action == "capture" || t.Action == "escape") {
		cw = 20
	}
	for _, m := range moves {
		if t.AvoidStaleKingWalk && isKingMove(obs, m) && staleThreatOn(obs, m[2:4], age) {
			continue
		}
		cv := captureValue(obs, m)
		if t.SuppressCaptureMax > 0 && cv > 0 && cv <= t.SuppressCaptureMax {
			continue
		}
		if t.PreferQuiet && cv > 0 && t.Action != "capture" && t.Action != "escape" {
			continue
		}
		if t.Action == "promote_queen" && !strings.HasSuffix(m, "q") && wantsPromotion(m) {
			continue
		}
		if t.Action == "promote_knight" && !strings.HasSuffix(m, "n") && wantsPromotion(m) {
			// still allow non-promo moves; prefer knight promos via score
		}
		sc := cv * cw
		if wantsPromotion(m) {
			if strings.HasSuffix(m, "q") {
				if t.Action == "promote_knight" {
					sc += 5
				} else {
					sc += 30
				}
			} else if strings.HasSuffix(m, "n") {
				if t.Action == "promote_knight" {
					sc += 35
				} else {
					sc += 12
				}
			} else {
				sc += 10
			}
		}
		if ek != "" && len(m) >= 4 && t.KingHuntWeight > 0 {
			sc += (7 - chebyshev(m[2:4], ek)) * t.KingHuntWeight
		}
		if isKingMove(obs, m) && obs.Check {
			sc += t.CheckEscapeBonus
			if t.CheckEscapeBonus == 0 && t.Action == "escape" {
				sc += 6
			}
		} else if isKingMove(obs, m) {
			sc -= t.KingMovePenalty
		}
		if t.Action == "escape" && !obs.Check {
			// still ok
		}
		if len(m) >= 4 {
			sc += int(m[3]-'1') % 3
		}
		if sc > bestScore || (sc == bestScore && m > best) {
			bestScore = sc
			best = m
		}
	}
	if best == "" {
		for _, m := range moves {
			if t.AvoidStaleKingWalk && isKingMove(obs, m) && staleThreatOn(obs, m[2:4], age) {
				continue
			}
			if best == "" || m > best {
				best = m
			}
		}
	}
	if best != "" {
		base.Move = best
		return base
	}
	if d := pickDrop(drops, king, true); d != nil {
		base.Drop = d
		return base
	}
	if len(moves) == 0 && len(drops) == 0 {
		base.Hold = true
		return base
	}
	if len(moves) > 0 {
		base.Move = moves[len(moves)-1]
		return base
	}
	base.Hold = true
	return base
}

func filterBoardMoves(in []string) []string {
	out := []string{}
	for _, m := range in {
		if strings.HasPrefix(m, "drop:") {
			continue
		}
		out = append(out, m)
	}
	return out
}

func materialKind(k string) int {
	switch k {
	case "p":
		return 1
	case "n", "b":
		return 3
	case "r":
		return 5
	case "q":
		return 9
	default:
		return 0
	}
}

func captureValue(obs Observation, uci string) int {
	if len(uci) < 4 {
		return 0
	}
	to := uci[2:4]
	for _, p := range obs.Pieces {
		if !p.Own && p.Square == to {
			return materialKind(p.Kind)
		}
	}
	return 0
}

func hasLegalCaptures(obs Observation) bool {
	for _, m := range obs.LegalMoves {
		if strings.HasPrefix(m, "drop:") {
			continue
		}
		if captureValue(obs, m) > 0 {
			return true
		}
	}
	return false
}

func hasPromotion(obs Observation) bool {
	for _, m := range obs.LegalMoves {
		if wantsPromotion(m) {
			return true
		}
	}
	return false
}

func wantsPromotion(uci string) bool {
	return len(uci) >= 5 && (uci[4] == 'q' || uci[4] == 'n' || uci[4] == 'r' || uci[4] == 'b')
}

func isKingMove(obs Observation, uci string) bool {
	if len(uci) < 4 {
		return false
	}
	from := uci[0:2]
	for _, p := range obs.Pieces {
		if p.Own && p.Kind == "k" && p.Square == from {
			return true
		}
	}
	return false
}

func ownKingSquare(pieces []PieceView) string {
	for _, p := range pieces {
		if p.Own && p.Kind == "k" {
			return p.Square
		}
	}
	return ""
}

func enemyKingSquare(pieces []PieceView) string {
	for _, p := range pieces {
		if !p.Own && p.Kind == "k" {
			return p.Square
		}
	}
	return ""
}

func chebyshev(a, b string) int {
	if len(a) != 2 || len(b) != 2 {
		return 7
	}
	df := int(a[0]) - int(b[0])
	dr := int(a[1]) - int(b[1])
	if df < 0 {
		df = -df
	}
	if dr < 0 {
		dr = -dr
	}
	if df > dr {
		return df
	}
	return dr
}

func staleThreatOn(obs Observation, sq string, ageMax int) bool {
	for _, s := range obs.Sightings {
		if s.Age <= ageMax && s.Square == sq {
			return true
		}
	}
	return false
}

func hasStaleNearKing(obs Observation, ageMax int) bool {
	king := ownKingSquare(obs.Pieces)
	if king == "" {
		return false
	}
	for _, s := range obs.Sightings {
		if s.Age <= ageMax && near(s.Square, king) {
			return true
		}
	}
	return false
}

func pickDrop(drops []string, king string, nearKing bool) *Drop {
	best := ""
	for _, d := range drops {
		if !strings.HasPrefix(d, "drop:") {
			continue
		}
		if best == "" || d < best {
			best = d
		}
		if nearKing && king != "" {
			rest := strings.TrimPrefix(d, "drop:")
			if len(rest) >= 3 && near(rest[1:], king) {
				best = d
				break
			}
		}
	}
	if best == "" {
		return nil
	}
	rest := strings.TrimPrefix(best, "drop:")
	return &Drop{Piece: rest[:1], Square: rest[1:]}
}

func near(a, b string) bool {
	if len(a) != 2 || len(b) != 2 {
		return false
	}
	df := int(a[0]) - int(b[0])
	dr := int(a[1]) - int(b[1])
	if df < 0 {
		df = -df
	}
	if dr < 0 {
		dr = -dr
	}
	return df <= 2 && dr <= 2
}
