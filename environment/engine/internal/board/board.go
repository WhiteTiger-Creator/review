package board

import (
	"fmt"
	"strings"
)

type Color int8

const (
	EmptyColor Color = 0
	White      Color = 1
	Black      Color = 2
)

func (c Color) Opponent() Color {
	if c == White {
		return Black
	}
	if c == Black {
		return White
	}
	return EmptyColor
}

func (c Color) String() string {
	switch c {
	case White:
		return "white"
	case Black:
		return "black"
	default:
		return "empty"
	}
}

func ParseColor(s string) (Color, error) {
	switch strings.ToLower(s) {
	case "white", "w":
		return White, nil
	case "black", "b":
		return Black, nil
	default:
		return EmptyColor, fmt.Errorf("invalid color %q", s)
	}
}

type Kind int8

const (
	Empty  Kind = 0
	Pawn   Kind = 1
	Knight Kind = 2
	Bishop Kind = 3
	Rook   Kind = 4
	Queen  Kind = 5
	King   Kind = 6
)

func (k Kind) String() string {
	switch k {
	case Pawn:
		return "p"
	case Knight:
		return "n"
	case Bishop:
		return "b"
	case Rook:
		return "r"
	case Queen:
		return "q"
	case King:
		return "k"
	default:
		return ""
	}
}

func ParseKind(s string) (Kind, error) {
	switch strings.ToLower(s) {
	case "p", "pawn":
		return Pawn, nil
	case "n", "knight":
		return Knight, nil
	case "b", "bishop":
		return Bishop, nil
	case "r", "rook":
		return Rook, nil
	case "q", "queen":
		return Queen, nil
	case "k", "king":
		return King, nil
	default:
		return Empty, fmt.Errorf("invalid kind %q", s)
	}
}

type Piece struct {
	Color Color  `json:"color"`
	Kind  Kind   `json:"kind"`
	ID    string `json:"id"`
}

func (p Piece) IsEmpty() bool { return p.Kind == Empty || p.Color == EmptyColor }

func (p Piece) FENChar() byte {
	if p.IsEmpty() {
		return '1'
	}
	ch := p.Kind.String()[0]
	if p.Color == White && ch >= 'a' && ch <= 'z' {
		ch = ch - 'a' + 'A'
	}
	return byte(ch)
}

type Square int8

const NoSquare Square = -1

func Sq(file, rank int) Square {
	if file < 0 || file > 7 || rank < 0 || rank > 7 {
		return NoSquare
	}
	return Square(rank*8 + file)
}

func (s Square) File() int {
	if s < 0 {
		return -1
	}
	return int(s) % 8
}

func (s Square) Rank() int {
	if s < 0 {
		return -1
	}
	return int(s) / 8
}

func (s Square) String() string {
	if s < 0 || s > 63 {
		return "-"
	}
	return string(rune('a'+s.File())) + string(rune('1'+s.Rank()))
}

func ParseSquare(s string) (Square, error) {
	s = strings.TrimSpace(strings.ToLower(s))
	if len(s) != 2 {
		return NoSquare, fmt.Errorf("invalid square %q", s)
	}
	f := int(s[0] - 'a')
	r := int(s[1] - '1')
	sq := Sq(f, r)
	if sq == NoSquare {
		return NoSquare, fmt.Errorf("invalid square %q", s)
	}
	return sq, nil
}

type CastlingRights struct {
	WhiteKingSide  bool `json:"white_king_side"`
	WhiteQueenSide bool `json:"white_queen_side"`
	BlackKingSide  bool `json:"black_king_side"`
	BlackQueenSide bool `json:"black_queen_side"`
}

type Board struct {
	Squares  [64]Piece      `json:"-"`
	Side     Color          `json:"side"`
	Castling CastlingRights `json:"castling"`
	EP       Square         `json:"ep"`
	Halfmove int            `json:"halfmove"`
	Fullmove int            `json:"fullmove"`
	BoardID  string         `json:"board_id"`
	RepHash  []uint64       `json:"-"`
}

func NewEmpty(id string) *Board {
	b := &Board{Side: White, EP: NoSquare, Fullmove: 1, BoardID: id}
	return b
}

func (b *Board) Clone() *Board {
	out := *b
	out.RepHash = append([]uint64{}, b.RepHash...)
	return &out
}

func (b *Board) At(sq Square) Piece {
	if sq < 0 || sq > 63 {
		return Piece{}
	}
	return b.Squares[sq]
}

func (b *Board) Set(sq Square, p Piece) {
	if sq >= 0 && sq <= 63 {
		b.Squares[sq] = p
	}
}

func (b *Board) FindKing(c Color) Square {
	for i := Square(0); i < 64; i++ {
		p := b.Squares[i]
		if p.Color == c && p.Kind == King {
			return i
		}
	}
	return NoSquare
}

func (b *Board) PieceList(c Color) []Square {
	out := make([]Square, 0, 16)
	for i := Square(0); i < 64; i++ {
		if b.Squares[i].Color == c {
			out = append(out, i)
		}
	}
	return out
}

func MaterialValue(k Kind) int {
	switch k {
	case Pawn:
		return 1
	case Knight, Bishop:
		return 3
	case Rook:
		return 5
	case Queen:
		return 9
	default:
		return 0
	}
}

func ReflectFile(sq Square) Square {
	if sq < 0 {
		return sq
	}
	return Sq(7-sq.File(), sq.Rank())
}
