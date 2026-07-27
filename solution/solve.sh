#!/bin/bash
set -euo pipefail

# Oracle installs a stronger belief-aware relay bot over the starter sources.
ROOT="/app/work/relaybot"
mkdir -p "$ROOT"

cat > "$ROOT/go.mod" <<'EOF'
module relaybot

go 1.24
EOF

cat > "$ROOT/belief.go" <<'EOF'
package main

func visibleSet(squares []string) map[string]bool {
	m := map[string]bool{}
	for _, s := range squares {
		m[s] = true
	}
	return m
}

func ownKingSquare(pieces []PieceView, side string) string {
	for _, p := range pieces {
		if p.Own && p.Kind == "k" {
			return p.Square
		}
	}
	return ""
}

func enemyOn(pieces []PieceView, sq string) bool {
	for _, p := range pieces {
		if !p.Own && p.Square == sq {
			return true
		}
	}
	return false
}

func staleThreatNearKing(obs Observation, king string) bool {
	if king == "" {
		return false
	}
	kf := int(king[0] - 'a')
	kr := int(king[1] - '1')
	for _, s := range obs.Sightings {
		if s.Age == 0 || len(s.Square) != 2 {
			continue
		}
		sf := int(s.Square[0] - 'a')
		sr := int(s.Square[1] - '1')
		df := kf - sf
		if df < 0 {
			df = -df
		}
		dr := kr - sr
		if dr < 0 {
			dr = -dr
		}
		if df <= 2 && dr <= 2 && s.Age <= 2 {
			return true
		}
	}
	return false
}
EOF

cat > "$ROOT/policy.go" <<'EOF'
package main

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

func wantsPromotion(uci string) bool {
	return len(uci) >= 5 && (uci[4] == 'q' || uci[4] == 'n' || uci[4] == 'r' || uci[4] == 'b')
}
EOF

cat > "$ROOT/main.go" <<'EOF'
package main

import (
	"bufio"
	"encoding/json"
	"os"
	"sort"
	"strings"
)

type Observation struct {
	Type           string      `json:"type"`
	Board          string      `json:"board"`
	Side           string      `json:"side"`
	Team           string      `json:"team"`
	Ply            int         `json:"ply"`
	Check          bool        `json:"check"`
	VisibleSquares []string    `json:"visible_squares"`
	Pieces         []PieceView `json:"pieces"`
	Sightings      []Sighting  `json:"stale_sightings"`
	ReadyDrops     []string    `json:"ready_drops"`
	LegalMoves     []string    `json:"legal_moves"`
	LegalDrops     []string    `json:"legal_drops"`
	QueueLen       int         `json:"queue_len"`
	QueueCapacity  int         `json:"queue_capacity"`
	RequestHint    string      `json:"request_hint"`
	Horizon        int         `json:"horizon"`
}

type PieceView struct {
	ID     string `json:"id"`
	Square string `json:"square"`
	Kind   string `json:"kind"`
	Color  string `json:"color"`
	Own    bool   `json:"own"`
}

type Sighting struct {
	Square string `json:"square"`
	Kind   string `json:"kind"`
	ID     string `json:"id"`
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
	in := bufio.NewScanner(os.Stdin)
	in.Buffer(make([]byte, 0, 1024*1024), 1024*1024)
	out := bufio.NewWriter(os.Stdout)
	lastRequest := ""
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
		act := choose(obs, &lastRequest)
		b, _ := json.Marshal(act)
		_, _ = out.Write(append(b, '\n'))
		_ = out.Flush()
	}
}

func choose(obs Observation, lastRequest *string) Action {
	base := Action{Type: "action", Board: obs.Board, Side: obs.Side}
	moves := filterBoardMoves(obs.LegalMoves)
	drops := append([]string{}, obs.LegalDrops...)
	sort.Strings(moves)
	sort.Strings(drops)
	king := ownKingSquare(obs.Pieces, obs.Side)
	ek := enemyKingSquare(obs.Pieces)

	if obs.Check {
		if mv := bestEscape(obs, moves, king); mv != "" {
			base.Move = mv
			return base
		}
		if d := defensiveDrop(obs, drops, king); d != nil {
			base.Drop = d
			return base
		}
	}

	// Emit an early request on busy boards so teammate capture bias is available.
	busy := len(obs.Pieces) >= 4
	if busy && obs.QueueLen < obs.QueueCapacity && len(obs.ReadyDrops) == 0 && obs.Ply <= 3 && !obs.Check {
		want := "q"
		if obs.RequestHint == "n" {
			want = "n"
		}
		base.Request = want
		*lastRequest = want
		return base
	}

	if len(drops) > 0 && (obs.Check || len(moves) == 0 || obs.Ply%3 == 0) {
		if d := defensiveDrop(obs, drops, king); d != nil {
			base.Drop = d
			return base
		}
	}

	best := ""
	bestScore := -1000
	for _, m := range moves {
		if isKingMove(obs, m) && staleThreatOn(obs, m[2:4]) {
			continue
		}
		sc := captureValue(obs, m) * 20
		if wantsPromotion(m) {
			if strings.HasSuffix(m, "q") {
				sc += 30
			} else {
				sc += 12
			}
		}
		if ek != "" && len(m) >= 4 {
			sc += (7 - chebyshev(m[2:4], ek)) * 3
		}
		if isKingMove(obs, m) && obs.Check {
			sc += 6
		} else if isKingMove(obs, m) {
			sc -= 4
		}
		if len(m) >= 4 {
			sc += int(m[3]-'1') % 3
		}
		if sc > bestScore || (sc == bestScore && m > best) {
			bestScore = sc
			best = m
		}
	}

	if best != "" {
		base.Move = best
		return base
	}
	if d := defensiveDrop(obs, drops, king); d != nil {
		base.Drop = d
		return base
	}
	if len(moves) > 0 {
		base.Move = moves[len(moves)-1]
		return base
	}
	if len(drops) > 0 {
		if d := defensiveDrop(obs, drops, king); d != nil {
			base.Drop = d
			return base
		}
	}
	base.Hold = true
	return base
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

func bestEscape(obs Observation, moves []string, king string) string {
	best := ""
	bestScore := -1000
	for _, m := range moves {
		if isKingMove(obs, m) && staleThreatOn(obs, m[2:4]) {
			continue
		}
		sc := captureValue(obs, m) * 10
		if isKingMove(obs, m) {
			sc += 3
		} else {
			sc += 8
		}
		if sc > bestScore || (sc == bestScore && m > best) {
			bestScore = sc
			best = m
		}
	}
	return best
}

func staleThreatOn(obs Observation, sq string) bool {
	for _, s := range obs.Sightings {
		if s.Age <= 2 && s.Square == sq {
			return true
		}
	}
	return false
}

func defensiveDrop(obs Observation, drops []string, king string) *Drop {
	best := ""
	for _, d := range drops {
		if !strings.HasPrefix(d, "drop:") {
			continue
		}
		if best == "" || d < best {
			best = d
		}
		rest := strings.TrimPrefix(d, "drop:")
		if len(rest) >= 3 && king != "" {
			sq := rest[1:]
			// prefer drops near king
			if near(sq, king) {
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
EOF

# Ensure offline compile works inside the environment.
cd "$ROOT"
CGO_ENABLED=0 go build -o /tmp/oracle-relaybot .
echo "oracle bot installed"
