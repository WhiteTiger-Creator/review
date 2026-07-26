package cartographer

// validateBoard reports whether board satisfies the public layout contract.
// The starter rejects clearly malformed boards but does not solve routes.
func validateBoard(board Board) bool {
	if board.Rows < 2 || board.Rows > 8 || board.Cols < 2 || board.Cols > 8 {
		return false
	}
	if len(board.Tiles) != board.Rows*board.Cols {
		return false
	}
	starts, exits, crumbles := 0, 0, 0
	keys := map[string]int{}
	portals := map[string]int{}
	for _, tile := range board.Tiles {
		switch tile.Kind {
		case TileFloor, TileWall, TileStart, TileExit, TileCrumble:
			if tile.Tag != "" {
				return false
			}
		case TileKey, TileDoor:
			if len(tile.Tag) != 1 || tile.Tag[0] < 'a' || tile.Tag[0] > 'd' {
				return false
			}
		case TilePortal:
			if len(tile.Tag) != 1 || tile.Tag[0] < 'a' || tile.Tag[0] > 'd' {
				return false
			}
		default:
			return false
		}
		switch tile.Kind {
		case TileStart:
			starts++
		case TileExit:
			exits++
		case TileCrumble:
			crumbles++
		case TileKey:
			keys[tile.Tag]++
		case TilePortal:
			portals[tile.Tag]++
		}
	}
	if starts != 1 || exits != 1 || crumbles > 12 {
		return false
	}
	for _, n := range keys {
		if n > 1 {
			return false
		}
	}
	for _, n := range portals {
		if n != 2 {
			return false
		}
	}
	return true
}
