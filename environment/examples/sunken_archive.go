package examples

import "opaline/cartographer"

// SunkenArchive uses collapsing floors that must be left carefully.
// Layout (3x4):
//   S C . .
//   . C . .
//   . . C E
func SunkenArchive() cartographer.Board {
	F := cartographer.Tile{Kind: cartographer.TileFloor}
	C := cartographer.Tile{Kind: cartographer.TileCrumble}
	return cartographer.Board{
		Rows: 3,
		Cols: 4,
		Tiles: []cartographer.Tile{
			{Kind: cartographer.TileStart}, C, F, F,
			F, C, F, F,
			F, F, C, {Kind: cartographer.TileExit},
		},
	}
}
