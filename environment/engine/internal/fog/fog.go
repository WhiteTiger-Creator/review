package fog

import (
	"sort"

	"fog-chess-relay/internal/board"
	"fog-chess-relay/internal/legal"
)

type Sighting struct {
	Square board.Square `json:"-"`
	SqName string       `json:"square"`
	Kind   string       `json:"kind"`
	Color  string       `json:"color"`
	ID     string       `json:"id"`
	Age    int          `json:"age"`
}

type View struct {
	Visible   []string   `json:"visible_squares"`
	Pieces    []PieceView `json:"pieces"`
	Sightings []Sighting `json:"stale_sightings"`
	Check     bool       `json:"check"`
}

type PieceView struct {
	ID     string `json:"id"`
	Square string `json:"square"`
	Kind   string `json:"kind"`
	Color  string `json:"color"`
	Own    bool   `json:"own"`
}

type Tracker struct {
	Sightings map[string]Sighting // key: piece id or square-kind
	Radius    int
}

func NewTracker(radius int) *Tracker {
	return &Tracker{Sightings: map[string]Sighting{}, Radius: radius}
}

func (t *Tracker) Clone() *Tracker {
	out := &Tracker{Radius: t.Radius, Sightings: map[string]Sighting{}}
	for k, v := range t.Sightings {
		out.Sightings[k] = v
	}
	return out
}

func VisibleMask(b *board.Board, viewer board.Color, radius int) [64]bool {
	var vis [64]bool
	att := legal.Attacks(b, viewer)
	for sq := board.Square(0); sq < 64; sq++ {
		p := b.At(sq)
		if p.Color == viewer {
			vis[sq] = true
			if radius > 0 {
				for df := -radius; df <= radius; df++ {
					for dr := -radius; dr <= radius; dr++ {
						to := board.Sq(sq.File()+df, sq.Rank()+dr)
						if to != board.NoSquare {
							vis[to] = true
						}
					}
				}
			}
		}
		if att[sq] {
			vis[sq] = true
		}
	}
	return vis
}

func (t *Tracker) Observe(b *board.Board, viewer board.Color, publicSquares []board.Square) View {
	vis := VisibleMask(b, viewer, t.Radius)
	for _, sq := range publicSquares {
		if sq >= 0 && sq < 64 {
			vis[sq] = true
		}
	}
	// age existing sightings
	for k, s := range t.Sightings {
		s.Age++
		t.Sightings[k] = s
	}
	pieces := []PieceView{}
	sqNames := []string{}
	for sq := board.Square(0); sq < 64; sq++ {
		if !vis[sq] {
			continue
		}
		sqNames = append(sqNames, sq.String())
		p := b.At(sq)
		if p.IsEmpty() {
			// clear sightings on now-empty visible squares
			for k, s := range t.Sightings {
				if s.Square == sq {
					delete(t.Sightings, k)
				}
			}
			continue
		}
		own := p.Color == viewer
		pieces = append(pieces, PieceView{
			ID: p.ID, Square: sq.String(), Kind: p.Kind.String(), Color: p.Color.String(), Own: own,
		})
		if !own {
			key := p.ID
			if key == "" {
				key = sq.String() + ":" + p.Kind.String()
			}
			t.Sightings[key] = Sighting{Square: sq, SqName: sq.String(), Kind: p.Kind.String(), Color: p.Color.String(), ID: p.ID, Age: 0}
		}
	}
	sort.Strings(sqNames)
	sort.Slice(pieces, func(i, j int) bool {
		if pieces[i].Square == pieces[j].Square {
			return pieces[i].ID < pieces[j].ID
		}
		return pieces[i].Square < pieces[j].Square
	})
	stale := []Sighting{}
	for _, s := range t.Sightings {
		if s.Age > 0 {
			if int(s.Square) >= 0 && int(s.Square) < 64 && vis[s.Square] {
				continue
			}
			stale = append(stale, s)
		}
	}
	sort.Slice(stale, func(i, j int) bool {
		if stale[i].Square == stale[j].Square {
			return stale[i].ID < stale[j].ID
		}
		return stale[i].Square < stale[j].Square
	})
	return View{
		Visible:   sqNames,
		Pieces:    pieces,
		Sightings: stale,
		Check:     legal.InCheck(b, viewer),
	}
}

func CompatibleHiddenBlocker(b *board.Board, viewer board.Color, from, to board.Square) bool {
	// True if some square on the sliding path is not visible and could hold a blocker.
	vis := VisibleMask(b, viewer, 0)
	df := sign(to.File() - from.File())
	dr := sign(to.Rank() - from.Rank())
	if df == 0 && dr == 0 {
		return false
	}
	// knights jump
	if abs(to.File()-from.File())+abs(to.Rank()-from.Rank()) == 3 &&
		abs(to.File()-from.File()) != 0 && abs(to.Rank()-from.Rank()) != 0 &&
		abs(to.File()-from.File()) != abs(to.Rank()-from.Rank()) {
		return false
	}
	f, r := from.File()+df, from.Rank()+dr
	for {
		sq := board.Sq(f, r)
		if sq == board.NoSquare || sq == to {
			break
		}
		if !vis[sq] {
			return true
		}
		if !b.At(sq).IsEmpty() {
			return true
		}
		f += df
		r += dr
	}
	return false
}

func sign(x int) int {
	if x < 0 {
		return -1
	}
	if x > 0 {
		return 1
	}
	return 0
}

func abs(x int) int {
	if x < 0 {
		return -x
	}
	return x
}
