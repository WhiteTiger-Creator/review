package cartographer

var moveDeltas = [...]Coord{
	MoveUp:    {Row: -1, Col: 0},
	MoveRight: {Row: 0, Col: 1},
	MoveDown:  {Row: 1, Col: 0},
	MoveLeft:  {Row: 0, Col: -1},
}

// CanonicalMoves lists the fixed lexicographic move order.
func CanonicalMoveOrder() []Move {
	return []Move{MoveUp, MoveRight, MoveDown, MoveLeft}
}
