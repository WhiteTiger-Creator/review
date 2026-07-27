package protocol

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"

	"fog-chess-relay/internal/board"
	"fog-chess-relay/internal/fog"
	"fog-chess-relay/internal/legal"
	"fog-chess-relay/internal/relay"
)

const MaxMessageBytes = 1 << 20

type Observation struct {
	Type           string           `json:"type"`
	MatchID        string           `json:"match_id"`
	Board          string           `json:"board"`
	Side           string           `json:"side"`
	Team           string           `json:"team"`
	Ply            int              `json:"ply"`
	Step           int              `json:"step"`
	Horizon        int              `json:"horizon"`
	VisibleSquares []string         `json:"visible_squares"`
	Pieces         []fog.PieceView  `json:"pieces"`
	Sightings      []fog.Sighting   `json:"stale_sightings"`
	Check          bool             `json:"check"`
	ReadyDrops     []string         `json:"ready_drops"`
	QueueDelay     int              `json:"queue_delay"`
	QueueCapacity  int              `json:"queue_capacity"`
	QueueLen       int              `json:"queue_len"`
	LegalMoves     []string         `json:"legal_moves"`
	LegalDrops     []string         `json:"legal_drops"`
	PublicEvents   []relay.Event    `json:"public_events"`
	RequestHint    string           `json:"request_hint,omitempty"`
	SeedHint       string           `json:"seed_hint,omitempty"`
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

type TerminalMsg struct {
	Type   string         `json:"type"`
	Reason string         `json:"reason"`
	Scores map[string]int `json:"scores"`
}

func Encode(w io.Writer, v any) error {
	b, err := json.Marshal(v)
	if err != nil {
		return err
	}
	if len(b) > MaxMessageBytes {
		return fmt.Errorf("message exceeds byte limit")
	}
	_, err = w.Write(append(b, '\n'))
	return err
}

func DecodeAction(r *bufio.Reader) (Action, error) {
	line, err := r.ReadBytes('\n')
	if err != nil {
		return Action{}, err
	}
	if len(line) > MaxMessageBytes {
		return Action{}, fmt.Errorf("action too large")
	}
	var a Action
	if err := json.Unmarshal(line, &a); err != nil {
		return Action{}, err
	}
	if a.Type != "action" {
		return Action{}, fmt.Errorf("expected action")
	}
	return a, nil
}

func ParseMoveAction(a Action) (legal.Move, error) {
	if a.Drop != nil {
		kind, err := board.ParseKind(a.Drop.Piece)
		if err != nil {
			return legal.Move{}, err
		}
		sq, err := board.ParseSquare(a.Drop.Square)
		if err != nil {
			return legal.Move{}, err
		}
		return legal.Move{IsDrop: true, DropKind: kind, To: sq}, nil
	}
	if a.Hold || a.Request != "" {
		return legal.Move{}, fmt.Errorf("not a board move")
	}
	m := a.Move
	if len(m) < 4 {
		return legal.Move{}, fmt.Errorf("bad move")
	}
	from, err := board.ParseSquare(m[0:2])
	if err != nil {
		return legal.Move{}, err
	}
	to, err := board.ParseSquare(m[2:4])
	if err != nil {
		return legal.Move{}, err
	}
	mv := legal.Move{From: from, To: to}
	if len(m) >= 5 {
		k, err := board.ParseKind(m[4:5])
		if err != nil {
			return legal.Move{}, err
		}
		mv.Promote = k
	}
	return mv, nil
}

func MoveStrings(moves []legal.Move) []string {
	out := make([]string, 0, len(moves))
	for _, m := range moves {
		out = append(out, m.UCI())
	}
	return out
}
