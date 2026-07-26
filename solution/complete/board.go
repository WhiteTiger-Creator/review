package cartographer

// Coord is a board cell addressed by row and column.
type Coord struct {
	Row int
	Col int
}

// TileKind classifies a single board cell.
type TileKind int

const (
	TileFloor TileKind = iota
	TileWall
	TileStart
	TileExit
	TileKey
	TileDoor
	TileCrumble
	TilePortal
)

// Tile is one cell in row-major board storage.
type Tile struct {
	Kind TileKind
	Tag  string
}

// Board is a compact rectangular dungeon layout.
type Board struct {
	Rows  int
	Cols  int
	Tiles []Tile
}
