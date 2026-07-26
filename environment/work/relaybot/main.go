package main

import (
	"bufio"
	"encoding/json"
	"os"
	"sort"
	"strings"
)

type Observation struct {
	Type           string          `json:"type"`
	Board          string          `json:"board"`
	Side           string          `json:"side"`
	Team           string          `json:"team"`
	Ply            int             `json:"ply"`
	Check          bool            `json:"check"`
	VisibleSquares []string        `json:"visible_squares"`
	Pieces         []PieceView     `json:"pieces"`
	Sightings      []Sighting      `json:"stale_sightings"`
	ReadyDrops     []string        `json:"ready_drops"`
	LegalMoves     []string        `json:"legal_moves"`
	LegalDrops     []string        `json:"legal_drops"`
	QueueLen       int             `json:"queue_len"`
	QueueCapacity  int             `json:"queue_capacity"`
	RequestHint    string          `json:"request_hint"`
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
		act := choose(obs)
		b, _ := json.Marshal(act)
		_, _ = out.Write(append(b, '\n'))
		_ = out.Flush()
	}
}

func choose(obs Observation) Action {
	base := Action{Type: "action", Board: obs.Board, Side: obs.Side}
	// Prefer simple captures among legal moves; avoid relying on stale sightings.
	moves := append([]string{}, obs.LegalMoves...)
	sort.Strings(moves)
	drops := append([]string{}, obs.LegalDrops...)
	sort.Strings(drops)

	if obs.Check {
		if mv := firstSafe(moves, obs); mv != "" {
			base.Move = stripDropPrefix(mv)
			return base
		}
		if d := firstDrop(drops); d != nil {
			base.Drop = d
			return base
		}
	}

	// Weak starter: avoid capturing when possible; play the lexicographically first quiet move.
	quiet := []string{}
	for _, m := range moves {
		if strings.HasPrefix(m, "drop:") {
			continue
		}
		to := ""
		if len(m) >= 4 {
			to = m[2:4]
		}
		capture := false
		for _, p := range obs.Pieces {
			if !p.Own && p.Square == to {
				capture = true
				break
			}
		}
		if !capture {
			quiet = append(quiet, m)
		}
	}
	if len(quiet) > 0 {
		base.Move = quiet[0]
		return base
	}
	if mv := firstSafe(moves, obs); mv != "" {
		base.Move = stripDropPrefix(mv)
		return base
	}
	if d := firstDrop(drops); d != nil {
		base.Drop = d
		return base
	}
	base.Hold = true
	return base
}

func stripDropPrefix(m string) string {
	if strings.HasPrefix(m, "drop:") {
		return ""
	}
	return m
}

func bestCapture(moves []string) string {
	for _, m := range moves {
		if strings.HasPrefix(m, "drop:") {
			continue
		}
		// heuristic: prefer moves toward center files when multiple; captures not labeled, so pick developing knight/bishop-like
	}
	for _, m := range moves {
		if strings.HasPrefix(m, "drop:") {
			continue
		}
		if len(m) >= 4 {
			// prefer any non-king shuffle ending on 3-6 ranks as "development"
			toRank := m[3]
			if toRank >= '3' && toRank <= '6' {
				return m
			}
		}
	}
	if len(moves) > 0 && !strings.HasPrefix(moves[0], "drop:") {
		return moves[0]
	}
	for _, m := range moves {
		if !strings.HasPrefix(m, "drop:") {
			return m
		}
	}
	return ""
}

func firstSafe(moves []string, obs Observation) string {
	stale := map[string]bool{}
	for _, s := range obs.Sightings {
		if s.Age > 2 {
			// ignore very stale for king safety heuristic by avoiding moving king next to them if we knew squares — starter just plays legal list
			_ = stale
		}
	}
	for _, m := range moves {
		if strings.HasPrefix(m, "drop:") {
			continue
		}
		return m
	}
	return ""
}

func firstDrop(drops []string) *Drop {
	for _, d := range drops {
		// format drop:n f6 via UCI drop:nf6
		if !strings.HasPrefix(d, "drop:") {
			continue
		}
		rest := strings.TrimPrefix(d, "drop:")
		if len(rest) < 3 {
			continue
		}
		return &Drop{Piece: rest[:1], Square: rest[1:]}
	}
	return nil
}
