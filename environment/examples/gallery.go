package examples

import "opaline/cartographer"

// Gallery is a small key-and-door chamber.
// Layout (3x4):
//   S . a .
//   # D # .
//   . . . E
// Key "a" opens door "a".
func Gallery() cartographer.Board {
	T := cartographer.Tile{}
	return cartographer.Board{
		Rows: 3,
		Cols: 4,
		Tiles: []cartographer.Tile{
			{Kind: cartographer.TileStart}, T, {Kind: cartographer.TileKey, Tag: "a"}, T,
			{Kind: cartographer.TileWall}, {Kind: cartographer.TileDoor, Tag: "a"}, {Kind: cartographer.TileWall}, T,
			T, T, T, {Kind: cartographer.TileExit},
		},
	}
}
