package board

import (
	"fmt"
	"strconv"
	"strings"
)

func (b *Board) ToFEN() string {
	var sb strings.Builder
	for rank := 7; rank >= 0; rank-- {
		empty := 0
		for file := 0; file < 8; file++ {
			p := b.Squares[Sq(file, rank)]
			if p.IsEmpty() {
				empty++
				continue
			}
			if empty > 0 {
				sb.WriteString(strconv.Itoa(empty))
				empty = 0
			}
			sb.WriteByte(p.FENChar())
		}
		if empty > 0 {
			sb.WriteString(strconv.Itoa(empty))
		}
		if rank > 0 {
			sb.WriteByte('/')
		}
	}
	sb.WriteByte(' ')
	if b.Side == White {
		sb.WriteByte('w')
	} else {
		sb.WriteByte('b')
	}
	sb.WriteByte(' ')
	cast := ""
	if b.Castling.WhiteKingSide {
		cast += "K"
	}
	if b.Castling.WhiteQueenSide {
		cast += "Q"
	}
	if b.Castling.BlackKingSide {
		cast += "k"
	}
	if b.Castling.BlackQueenSide {
		cast += "q"
	}
	if cast == "" {
		cast = "-"
	}
	sb.WriteString(cast)
	sb.WriteByte(' ')
	if b.EP == NoSquare {
		sb.WriteByte('-')
	} else {
		sb.WriteString(b.EP.String())
	}
	sb.WriteByte(' ')
	sb.WriteString(strconv.Itoa(b.Halfmove))
	sb.WriteByte(' ')
	sb.WriteString(strconv.Itoa(b.Fullmove))
	return sb.String()
}

func ParseFEN(fen, boardID string) (*Board, error) {
	parts := strings.Fields(fen)
	if len(parts) < 4 {
		return nil, fmt.Errorf("invalid fen")
	}
	b := NewEmpty(boardID)
	ranks := strings.Split(parts[0], "/")
	if len(ranks) != 8 {
		return nil, fmt.Errorf("invalid fen ranks")
	}
	idCounter := 0
	for ri, rankStr := range ranks {
		rank := 7 - ri
		file := 0
		for _, ch := range rankStr {
			if ch >= '1' && ch <= '8' {
				file += int(ch - '0')
				continue
			}
			if file > 7 {
				return nil, fmt.Errorf("fen overflow")
			}
			var color Color
			var kind Kind
			switch ch {
			case 'P':
				color, kind = White, Pawn
			case 'N':
				color, kind = White, Knight
			case 'B':
				color, kind = White, Bishop
			case 'R':
				color, kind = White, Rook
			case 'Q':
				color, kind = White, Queen
			case 'K':
				color, kind = White, King
			case 'p':
				color, kind = Black, Pawn
			case 'n':
				color, kind = Black, Knight
			case 'b':
				color, kind = Black, Bishop
			case 'r':
				color, kind = Black, Rook
			case 'q':
				color, kind = Black, Queen
			case 'k':
				color, kind = Black, King
			default:
				return nil, fmt.Errorf("bad fen piece %c", ch)
			}
			idCounter++
			b.Set(Sq(file, rank), Piece{
				Color: color,
				Kind:  kind,
				ID:    fmt.Sprintf("%s-%s%d", boardID, kind.String(), idCounter),
			})
			file++
		}
		if file != 8 {
			return nil, fmt.Errorf("fen rank width")
		}
	}
	side, err := ParseColor(parts[1])
	if err != nil {
		return nil, err
	}
	b.Side = side
	if parts[2] != "-" {
		for _, ch := range parts[2] {
			switch ch {
			case 'K':
				b.Castling.WhiteKingSide = true
			case 'Q':
				b.Castling.WhiteQueenSide = true
			case 'k':
				b.Castling.BlackKingSide = true
			case 'q':
				b.Castling.BlackQueenSide = true
			default:
				return nil, fmt.Errorf("bad castling")
			}
		}
	}
	if parts[3] == "-" {
		b.EP = NoSquare
	} else {
		ep, err := ParseSquare(parts[3])
		if err != nil {
			return nil, err
		}
		b.EP = ep
	}
	if len(parts) >= 5 {
		b.Halfmove, _ = strconv.Atoi(parts[4])
	}
	if len(parts) >= 6 {
		b.Fullmove, _ = strconv.Atoi(parts[5])
	}
	if b.Fullmove <= 0 {
		b.Fullmove = 1
	}
	return b, nil
}

func ValidateBasic(b *Board) error {
	wk, bk := 0, 0
	occ := map[Square]bool{}
	for i := Square(0); i < 64; i++ {
		p := b.Squares[i]
		if p.IsEmpty() {
			continue
		}
		if occ[i] {
			return fmt.Errorf("duplicate occupancy")
		}
		occ[i] = true
		if p.Kind == King {
			if p.Color == White {
				wk++
			} else {
				bk++
			}
		}
		if p.Kind == Pawn {
			r := i.Rank()
			if r == 0 || r == 7 {
				return fmt.Errorf("impossible pawn on %s", i)
			}
		}
	}
	if wk != 1 || bk != 1 {
		return fmt.Errorf("illegal kings count")
	}
	return nil
}
