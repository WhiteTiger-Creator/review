package relay

import (
	"sort"

	"fog-chess-relay/internal/board"
)

type QueuedPiece struct {
	Kind      board.Kind `json:"kind"`
	ID        string     `json:"id"`
	ReadyAt   int        `json:"ready_at"`
	SourceBoard string   `json:"source_board"`
}

type Queue struct {
	Team     string        `json:"team"`
	Capacity int           `json:"capacity"`
	Delay    int           `json:"delay"`
	Items    []QueuedPiece `json:"items"`
	PendingScore int       `json:"pending_score"`
}

type Event struct {
	Kind   string `json:"kind"`
	Team   string `json:"team"`
	Piece  string `json:"piece"`
	Board  string `json:"board"`
	Step   int    `json:"step"`
	Square string `json:"square,omitempty"`
}

type Manager struct {
	Queues map[string]*Queue
	Events []Event
	Step   int
}

func NewManager(capacity, delay int) *Manager {
	return &Manager{
		Queues: map[string]*Queue{
			"team_a": {Team: "team_a", Capacity: capacity, Delay: delay},
			"team_b": {Team: "team_b", Capacity: capacity, Delay: delay},
		},
		Events: []Event{},
		Step:   0,
	}
}

func (m *Manager) Clone() *Manager {
	out := &Manager{Step: m.Step, Events: append([]Event{}, m.Events...), Queues: map[string]*Queue{}}
	for k, q := range m.Queues {
		nq := *q
		nq.Items = append([]QueuedPiece{}, q.Items...)
		out.Queues[k] = &nq
	}
	return out
}

func (m *Manager) Advance() {
	m.Step++
}

func (m *Manager) Capture(team, sourceBoard, id string, kind board.Kind) bool {
	if kind == board.King || kind == board.Empty {
		return false
	}
	q := m.Queues[team]
	if q == nil {
		return false
	}
	ev := Event{Kind: "capture_to_relay", Team: team, Piece: kind.String(), Board: sourceBoard, Step: m.Step}
	m.Events = append(m.Events, ev)
	if len(q.Items) >= q.Capacity {
		q.PendingScore += board.MaterialValue(kind)
		return false
	}
	q.Items = append(q.Items, QueuedPiece{
		Kind: kind, ID: id, ReadyAt: m.Step + q.Delay, SourceBoard: sourceBoard,
	})
	sort.SliceStable(q.Items, func(i, j int) bool {
		if q.Items[i].ReadyAt == q.Items[j].ReadyAt {
			return q.Items[i].ID < q.Items[j].ID
		}
		return q.Items[i].ReadyAt < q.Items[j].ReadyAt
	})
	return true
}

func (m *Manager) Ready(team string) []QueuedPiece {
	q := m.Queues[team]
	if q == nil {
		return nil
	}
	out := []QueuedPiece{}
	for _, it := range q.Items {
		if it.ReadyAt <= m.Step {
			out = append(out, it)
		}
	}
	return out
}

func (m *Manager) Consume(team string, kind board.Kind) (QueuedPiece, bool) {
	q := m.Queues[team]
	if q == nil {
		return QueuedPiece{}, false
	}
	for i, it := range q.Items {
		if it.ReadyAt <= m.Step && it.Kind == kind {
			m.Events = append(m.Events, Event{Kind: "drop", Team: team, Piece: kind.String(), Board: "", Step: m.Step})
			q.Items = append(q.Items[:i], q.Items[i+1:]...)
			return it, true
		}
	}
	return QueuedPiece{}, false
}

func (m *Manager) PublicSquares() []board.Square {
	return nil
}

func TeamForCapture(capturingColor board.Color, boardID string, teamAWhiteOn string) string {
	// team_a is white on teamAWhiteOn board and black on the other.
	if boardID == teamAWhiteOn {
		if capturingColor == board.White {
			return "team_a"
		}
		return "team_b"
	}
	if capturingColor == board.Black {
		return "team_a"
	}
	return "team_b"
}

func DropBoardForTeam(team, teamAWhiteOn, otherBoard string) string {
	// Captures on one board feed drops on the teammate board.
	if team == "team_a" {
		if teamAWhiteOn == "alpha" {
			return "beta"
		}
		return "alpha"
	}
	if teamAWhiteOn == "alpha" {
		return "alpha"
	}
	return "beta"
}
