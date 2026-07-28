package legal

import (
	"fog-chess-relay/internal/board"
)

type Move struct {
	From      board.Square `json:"from"`
	To        board.Square `json:"to"`
	Promote   board.Kind   `json:"promote,omitempty"`
	DropKind  board.Kind   `json:"drop_kind,omitempty"`
	IsDrop    bool         `json:"is_drop"`
	IsCastle  bool         `json:"is_castle"`
	IsEP      bool         `json:"is_ep"`
	Capture   board.Kind   `json:"capture,omitempty"`
}

func (m Move) UCI() string {
	if m.IsDrop {
		return "drop:" + m.DropKind.String() + m.To.String()
	}
	s := m.From.String() + m.To.String()
	if m.Promote != board.Empty {
		s += m.Promote.String()
	}
	return s
}

var knightD = [][2]int{{1, 2}, {2, 1}, {-1, 2}, {-2, 1}, {1, -2}, {2, -1}, {-1, -2}, {-2, -1}}
var kingD = [][2]int{{1, 0}, {-1, 0}, {0, 1}, {0, -1}, {1, 1}, {1, -1}, {-1, 1}, {-1, -1}}
var bishopD = [][2]int{{1, 1}, {1, -1}, {-1, 1}, {-1, -1}}
var rookD = [][2]int{{1, 0}, {-1, 0}, {0, 1}, {0, -1}}

func PseudoMoves(b *board.Board, sq board.Square) []Move {
	p := b.At(sq)
	if p.IsEmpty() {
		return nil
	}
	out := make([]Move, 0, 16)
	switch p.Kind {
	case board.Pawn:
		out = append(out, pawnMoves(b, sq, p)...)
	case board.Knight:
		out = append(out, leapMoves(b, sq, p, knightD)...)
	case board.Bishop:
		out = append(out, slideMoves(b, sq, p, bishopD)...)
	case board.Rook:
		out = append(out, slideMoves(b, sq, p, rookD)...)
	case board.Queen:
		out = append(out, slideMoves(b, sq, p, bishopD)...)
		out = append(out, slideMoves(b, sq, p, rookD)...)
	case board.King:
		out = append(out, leapMoves(b, sq, p, kingD)...)
		out = append(out, castleMoves(b, sq, p)...)
	}
	return out
}

func pawnMoves(b *board.Board, sq board.Square, p board.Piece) []Move {
	dir := 1
	start, last := 1, 7
	if p.Color == board.Black {
		dir = -1
		start, last = 6, 0
	}
	out := []Move{}
	fwd := board.Sq(sq.File(), sq.Rank()+dir)
	if fwd != board.NoSquare && b.At(fwd).IsEmpty() {
		if sq.Rank()+dir == last {
			for _, pr := range []board.Kind{board.Queen, board.Rook, board.Bishop, board.Knight} {
				out = append(out, Move{From: sq, To: fwd, Promote: pr})
			}
		} else {
			out = append(out, Move{From: sq, To: fwd})
			if sq.Rank() == start {
				fwd2 := board.Sq(sq.File(), sq.Rank()+2*dir)
				if fwd2 != board.NoSquare && b.At(fwd2).IsEmpty() {
					out = append(out, Move{From: sq, To: fwd2})
				}
			}
		}
	}
	for _, df := range []int{-1, 1} {
		to := board.Sq(sq.File()+df, sq.Rank()+dir)
		if to == board.NoSquare {
			continue
		}
		cap := b.At(to)
		if !cap.IsEmpty() && cap.Color != p.Color {
			if sq.Rank()+dir == last {
				for _, pr := range []board.Kind{board.Queen, board.Rook, board.Bishop, board.Knight} {
					out = append(out, Move{From: sq, To: to, Promote: pr, Capture: cap.Kind})
				}
			} else {
				out = append(out, Move{From: sq, To: to, Capture: cap.Kind})
			}
		} else if to == b.EP {
			out = append(out, Move{From: sq, To: to, IsEP: true, Capture: board.Pawn})
		}
	}
	return out
}

func leapMoves(b *board.Board, sq board.Square, p board.Piece, deltas [][2]int) []Move {
	out := []Move{}
	for _, d := range deltas {
		to := board.Sq(sq.File()+d[0], sq.Rank()+d[1])
		if to == board.NoSquare {
			continue
		}
		t := b.At(to)
		if t.IsEmpty() {
			out = append(out, Move{From: sq, To: to})
		} else if t.Color != p.Color {
			out = append(out, Move{From: sq, To: to, Capture: t.Kind})
		}
	}
	return out
}

func slideMoves(b *board.Board, sq board.Square, p board.Piece, deltas [][2]int) []Move {
	out := []Move{}
	for _, d := range deltas {
		f, r := sq.File()+d[0], sq.Rank()+d[1]
		for {
			to := board.Sq(f, r)
			if to == board.NoSquare {
				break
			}
			t := b.At(to)
			if t.IsEmpty() {
				out = append(out, Move{From: sq, To: to})
			} else {
				if t.Color != p.Color {
					out = append(out, Move{From: sq, To: to, Capture: t.Kind})
				}
				break
			}
			f += d[0]
			r += d[1]
		}
	}
	return out
}

func castleMoves(b *board.Board, sq board.Square, p board.Piece) []Move {
	out := []Move{}
	rank := sq.Rank()
	if p.Color == board.White && rank == 0 && sq.File() == 4 {
		if b.Castling.WhiteKingSide && clear(b, []board.Square{board.Sq(5, 0), board.Sq(6, 0)}) {
			out = append(out, Move{From: sq, To: board.Sq(6, 0), IsCastle: true})
		}
		if b.Castling.WhiteQueenSide && clear(b, []board.Square{board.Sq(1, 0), board.Sq(2, 0), board.Sq(3, 0)}) {
			out = append(out, Move{From: sq, To: board.Sq(2, 0), IsCastle: true})
		}
	}
	if p.Color == board.Black && rank == 7 && sq.File() == 4 {
		if b.Castling.BlackKingSide && clear(b, []board.Square{board.Sq(5, 7), board.Sq(6, 7)}) {
			out = append(out, Move{From: sq, To: board.Sq(6, 7), IsCastle: true})
		}
		if b.Castling.BlackQueenSide && clear(b, []board.Square{board.Sq(1, 7), board.Sq(2, 7), board.Sq(3, 7)}) {
			out = append(out, Move{From: sq, To: board.Sq(2, 7), IsCastle: true})
		}
	}
	return out
}

func clear(b *board.Board, sqs []board.Square) bool {
	for _, s := range sqs {
		if !b.At(s).IsEmpty() {
			return false
		}
	}
	return true
}

func Attacks(b *board.Board, by board.Color) [64]bool {
	var att [64]bool
	for sq := board.Square(0); sq < 64; sq++ {
		p := b.At(sq)
		if p.Color != by {
			continue
		}
		if p.Kind == board.Pawn {
			dir := 1
			if by == board.Black {
				dir = -1
			}
			for _, df := range []int{-1, 1} {
				to := board.Sq(sq.File()+df, sq.Rank()+dir)
				if to != board.NoSquare {
					att[to] = true
				}
			}
			continue
		}
		for _, m := range PseudoMoves(b, sq) {
			if p.Kind == board.King && m.IsCastle {
				continue
			}
			att[m.To] = true
		}
	}
	return att
}

func InCheck(b *board.Board, c board.Color) bool {
	k := b.FindKing(c)
	if k == board.NoSquare {
		return true
	}
	att := Attacks(b, c.Opponent())
	return att[k]
}

func Apply(b *board.Board, m Move) (*board.Board, board.Piece) {
	nb := b.Clone()
	var captured board.Piece
	if m.IsDrop {
		nb.Set(m.To, board.Piece{Color: nb.Side, Kind: m.DropKind, ID: "drop-" + m.DropKind.String() + m.To.String()})
		nb.EP = board.NoSquare
		nb.Halfmove++
		if nb.Side == board.Black {
			nb.Fullmove++
		}
		nb.Side = nb.Side.Opponent()
		return nb, captured
	}
	p := nb.At(m.From)
	captured = nb.At(m.To)
	if m.IsEP {
		capSq := board.Sq(m.To.File(), m.From.Rank())
		captured = nb.At(capSq)
		nb.Set(capSq, board.Piece{})
	}
	nb.Set(m.To, p)
	nb.Set(m.From, board.Piece{})
	if m.IsCastle {
		if m.To.File() == 6 {
			rookFrom := board.Sq(7, m.From.Rank())
			rookTo := board.Sq(5, m.From.Rank())
			nb.Set(rookTo, nb.At(rookFrom))
			nb.Set(rookFrom, board.Piece{})
		} else if m.To.File() == 2 {
			rookFrom := board.Sq(0, m.From.Rank())
			rookTo := board.Sq(3, m.From.Rank())
			nb.Set(rookTo, nb.At(rookFrom))
			nb.Set(rookFrom, board.Piece{})
		}
	}
	if m.Promote != board.Empty {
		np := nb.At(m.To)
		np.Kind = m.Promote
		nb.Set(m.To, np)
	}
	// castling rights
	if p.Kind == board.King {
		if p.Color == board.White {
			nb.Castling.WhiteKingSide = false
			nb.Castling.WhiteQueenSide = false
		} else {
			nb.Castling.BlackKingSide = false
			nb.Castling.BlackQueenSide = false
		}
	}
	if p.Kind == board.Rook || captured.Kind == board.Rook {
		updateRookRights(nb, m.From)
		updateRookRights(nb, m.To)
	}
	nb.EP = board.NoSquare
	if p.Kind == board.Pawn && abs(m.To.Rank()-m.From.Rank()) == 2 {
		nb.EP = board.Sq(m.From.File(), (m.From.Rank()+m.To.Rank())/2)
	}
	if p.Kind == board.Pawn || !captured.IsEmpty() {
		nb.Halfmove = 0
	} else {
		nb.Halfmove++
	}
	if nb.Side == board.Black {
		nb.Fullmove++
	}
	nb.Side = nb.Side.Opponent()
	return nb, captured
}

func updateRookRights(b *board.Board, sq board.Square) {
	switch sq {
	case board.Sq(0, 0):
		b.Castling.WhiteQueenSide = false
	case board.Sq(7, 0):
		b.Castling.WhiteKingSide = false
	case board.Sq(0, 7):
		b.Castling.BlackQueenSide = false
	case board.Sq(7, 7):
		b.Castling.BlackKingSide = false
	}
}

func abs(x int) int {
	if x < 0 {
		return -x
	}
	return x
}

func LegalMoves(b *board.Board) []Move {
	out := make([]Move, 0, 64)
	side := b.Side
	for sq := board.Square(0); sq < 64; sq++ {
		p := b.At(sq)
		if p.Color != side {
			continue
		}
		for _, m := range PseudoMoves(b, sq) {
			if m.IsCastle {
				if InCheck(b, side) {
					continue
				}
				through := board.Sq((m.From.File()+m.To.File())/2, m.From.Rank())
				nb1, _ := Apply(b, Move{From: m.From, To: through})
				// Apply flips side; restore check for original side on intermediate
				nb1.Side = side
				if InCheck(nb1, side) {
					continue
				}
			}
			nb, _ := Apply(b, m)
			nb.Side = side // check own king after move before side flip already happened
			// Apply already flipped side; king of mover is opponent of nb.Side
			if InCheck(nb, side) {
				continue
			}
			out = append(out, m)
		}
	}
	return out
}

func LegalDrops(b *board.Board, kind board.Kind) []Move {
	if kind == board.Empty || kind == board.King {
		return nil
	}
	out := []Move{}
	side := b.Side
	for sq := board.Square(0); sq < 64; sq++ {
		if !b.At(sq).IsEmpty() {
			continue
		}
		if kind == board.Pawn && (sq.Rank() == 0 || sq.Rank() == 7) {
			continue
		}
		m := Move{To: sq, DropKind: kind, IsDrop: true}
		nb, _ := Apply(b, m)
		if InCheck(nb, side) {
			continue
		}
		out = append(out, m)
	}
	return out
}

func IsCheckmate(b *board.Board) bool {
	return InCheck(b, b.Side) && len(LegalMoves(b)) == 0
}

func IsStalemate(b *board.Board) bool {
	return !InCheck(b, b.Side) && len(LegalMoves(b)) == 0
}

func ZobristLike(b *board.Board) uint64 {
	var h uint64 = 14695981039346656037
	for i := board.Square(0); i < 64; i++ {
		p := b.At(i)
		if p.IsEmpty() {
			continue
		}
		h ^= uint64(i+1) * 1315423911
		h ^= uint64(p.Color) * 2654435761
		h ^= uint64(p.Kind) * 1597334677
	}
	h ^= uint64(b.Side) * 2246822519
	if b.Castling.WhiteKingSide {
		h ^= 3266489917
	}
	if b.Castling.WhiteQueenSide {
		h ^= 668265263
	}
	if b.Castling.BlackKingSide {
		h ^= 374761393
	}
	if b.Castling.BlackQueenSide {
		h ^= 0x9e3779b97f4a7c15
	}
	if b.EP != board.NoSquare {
		h ^= uint64(b.EP+3) * 0x85ebca77c2b2ae63
	}
	return h
}
