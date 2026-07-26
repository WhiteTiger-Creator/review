package main

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"strings"

	"opaline/cartographer"
)

type jsonCoord struct {
	Row int `json:"row"`
	Col int `json:"col"`
}

type jsonTile struct {
	Kind int    `json:"kind"`
	Tag  string `json:"tag"`
}

type jsonBoard struct {
	Rows  int        `json:"rows"`
	Cols  int        `json:"cols"`
	Tiles []jsonTile `json:"tiles"`
}

type jsonTraceStep struct {
	Index     int         `json:"index"`
	Move      int         `json:"move"`
	From      jsonCoord   `json:"from"`
	To        jsonCoord   `json:"to"`
	Keys      []string    `json:"keys"`
	Collapsed []jsonCoord `json:"collapsed"`
}

type jsonLanding struct {
	Step int       `json:"step"`
	At   jsonCoord `json:"at"`
}

type jsonDecision struct {
	Step         int       `json:"step"`
	At           jsonCoord `json:"at"`
	Alternatives []int     `json:"alternatives"`
}

type jsonAnalysis struct {
	Status            int              `json:"status"`
	Distance          int              `json:"distance"`
	ShortestCount     string           `json:"shortest_count"`
	CanonicalMoves    []int            `json:"canonical_moves"`
	Trace             []jsonTraceStep  `json:"trace"`
	MandatoryLandings []jsonLanding    `json:"mandatory_landings"`
	DecisionPoints    []jsonDecision   `json:"decision_points"`
}

type jsonRequest struct {
	Op        string       `json:"op"`
	Board     jsonBoard    `json:"board"`
	Candidate *jsonAnalysis `json:"candidate"`
}

type jsonResponse struct {
	Analysis *jsonAnalysis `json:"analysis,omitempty"`
	Valid    *int          `json:"validation,omitempty"`
	BoardOK  bool          `json:"board_unchanged"`
	Error    string        `json:"error,omitempty"`
}

func main() {
	raw, err := io.ReadAll(os.Stdin)
	if err != nil {
		fail(2, fmt.Sprintf("read stdin: %v", err))
	}
	var req jsonRequest
	if err := json.Unmarshal(raw, &req); err != nil {
		fail(2, fmt.Sprintf("decode: %v", err))
	}
	board := toBoard(req.Board)
	before := snapshot(board)

	switch strings.ToLower(req.Op) {
	case "analyze":
		out := fromAnalysis(cartographer.Analyze(board))
		ok := unchanged(before, board)
		enc := json.NewEncoder(os.Stdout)
		enc.SetEscapeHTML(false)
		_ = enc.Encode(jsonResponse{Analysis: &out, BoardOK: ok})
	case "validate":
		if req.Candidate == nil {
			fail(2, "missing candidate")
		}
		cand := toAnalysis(*req.Candidate)
		v := int(cartographer.Validate(board, cand))
		ok := unchanged(before, board)
		enc := json.NewEncoder(os.Stdout)
		enc.SetEscapeHTML(false)
		_ = enc.Encode(jsonResponse{Valid: &v, BoardOK: ok})
	case "analyze_validate":
		a := cartographer.Analyze(board)
		out := fromAnalysis(a)
		v := int(cartographer.Validate(board, a))
		ok := unchanged(before, board)
		enc := json.NewEncoder(os.Stdout)
		enc.SetEscapeHTML(false)
		_ = enc.Encode(jsonResponse{Analysis: &out, Valid: &v, BoardOK: ok})
	default:
		fail(2, "unknown op")
	}
}

func fail(code int, msg string) {
	enc := json.NewEncoder(os.Stdout)
	_ = enc.Encode(jsonResponse{Error: msg, BoardOK: false})
	os.Exit(code)
}

func toBoard(b jsonBoard) cartographer.Board {
	tiles := make([]cartographer.Tile, len(b.Tiles))
	for i, t := range b.Tiles {
		tiles[i] = cartographer.Tile{Kind: cartographer.TileKind(t.Kind), Tag: t.Tag}
	}
	return cartographer.Board{Rows: b.Rows, Cols: b.Cols, Tiles: tiles}
}

func fromAnalysis(a cartographer.Analysis) jsonAnalysis {
	moves := make([]int, len(a.CanonicalMoves))
	for i, m := range a.CanonicalMoves {
		moves[i] = int(m)
	}
	if moves == nil {
		moves = []int{}
	}
	trace := make([]jsonTraceStep, 0, len(a.Trace))
	for _, s := range a.Trace {
		keys := make([]string, len(s.Keys))
		copy(keys, s.Keys)
		if keys == nil {
			keys = []string{}
		}
		collapsed := make([]jsonCoord, len(s.Collapsed))
		for j, c := range s.Collapsed {
			collapsed[j] = jsonCoord{Row: c.Row, Col: c.Col}
		}
		if collapsed == nil {
			collapsed = []jsonCoord{}
		}
		trace = append(trace, jsonTraceStep{
			Index: s.Index, Move: int(s.Move),
			From: jsonCoord{Row: s.From.Row, Col: s.From.Col},
			To:   jsonCoord{Row: s.To.Row, Col: s.To.Col},
			Keys: keys, Collapsed: collapsed,
		})
	}
	lands := make([]jsonLanding, 0, len(a.MandatoryLandings))
	for _, l := range a.MandatoryLandings {
		lands = append(lands, jsonLanding{Step: l.Step, At: jsonCoord{Row: l.At.Row, Col: l.At.Col}})
	}
	decs := make([]jsonDecision, 0, len(a.DecisionPoints))
	for _, d := range a.DecisionPoints {
		alts := make([]int, len(d.Alternatives))
		for j, m := range d.Alternatives {
			alts[j] = int(m)
		}
		if alts == nil {
			alts = []int{}
		}
		decs = append(decs, jsonDecision{
			Step: d.Step, At: jsonCoord{Row: d.At.Row, Col: d.At.Col}, Alternatives: alts,
		})
	}
	return jsonAnalysis{
		Status: int(a.Status), Distance: a.Distance, ShortestCount: a.ShortestCount,
		CanonicalMoves: moves, Trace: trace, MandatoryLandings: lands, DecisionPoints: decs,
	}
}

func toAnalysis(a jsonAnalysis) cartographer.Analysis {
	moves := make([]cartographer.Move, len(a.CanonicalMoves))
	for i, m := range a.CanonicalMoves {
		moves[i] = cartographer.Move(m)
	}
	trace := make([]cartographer.TraceStep, len(a.Trace))
	for i, s := range a.Trace {
		keys := append([]string(nil), s.Keys...)
		collapsed := make([]cartographer.Coord, len(s.Collapsed))
		for j, c := range s.Collapsed {
			collapsed[j] = cartographer.Coord{Row: c.Row, Col: c.Col}
		}
		if keys == nil {
			keys = []string{}
		}
		if collapsed == nil {
			collapsed = []cartographer.Coord{}
		}
		trace[i] = cartographer.TraceStep{
			Index: s.Index, Move: cartographer.Move(s.Move),
			From: cartographer.Coord{Row: s.From.Row, Col: s.From.Col},
			To:   cartographer.Coord{Row: s.To.Row, Col: s.To.Col},
			Keys: keys, Collapsed: collapsed,
		}
	}
	lands := make([]cartographer.MandatoryLanding, len(a.MandatoryLandings))
	for i, l := range a.MandatoryLandings {
		lands[i] = cartographer.MandatoryLanding{
			Step: l.Step, At: cartographer.Coord{Row: l.At.Row, Col: l.At.Col},
		}
	}
	decs := make([]cartographer.DecisionPoint, len(a.DecisionPoints))
	for i, d := range a.DecisionPoints {
		alts := make([]cartographer.Move, len(d.Alternatives))
		for j, m := range d.Alternatives {
			alts[j] = cartographer.Move(m)
		}
		if alts == nil {
			alts = []cartographer.Move{}
		}
		decs[i] = cartographer.DecisionPoint{
			Step: d.Step, At: cartographer.Coord{Row: d.At.Row, Col: d.At.Col}, Alternatives: alts,
		}
	}
	if moves == nil {
		moves = []cartographer.Move{}
	}
	if trace == nil {
		trace = []cartographer.TraceStep{}
	}
	if lands == nil {
		lands = []cartographer.MandatoryLanding{}
	}
	if decs == nil {
		decs = []cartographer.DecisionPoint{}
	}
	return cartographer.Analysis{
		Status: cartographer.Status(a.Status), Distance: a.Distance, ShortestCount: a.ShortestCount,
		CanonicalMoves: moves, Trace: trace, MandatoryLandings: lands, DecisionPoints: decs,
	}
}

func snapshot(b cartographer.Board) []cartographer.Tile {
	out := make([]cartographer.Tile, len(b.Tiles))
	copy(out, b.Tiles)
	return out
}

func unchanged(before []cartographer.Tile, b cartographer.Board) bool {
	if len(before) != len(b.Tiles) {
		return false
	}
	for i := range before {
		if before[i] != b.Tiles[i] {
			return false
		}
	}
	return true
}
