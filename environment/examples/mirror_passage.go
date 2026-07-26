package examples

import "opaline/cartographer"

// MirrorPassage demonstrates paired portals.
// Layout (3x4):
//   S . Pa .
//   # # # #
//   . Pb . E
// Portal tag "a" links the two Pa/Pb cells.
func MirrorPassage() cartographer.Board {
	F := cartographer.Tile{Kind: cartographer.TileFloor}
	W := cartographer.Tile{Kind: cartographer.TileWall}
	P := func() cartographer.Tile { return cartographer.Tile{Kind: cartographer.TilePortal, Tag: "a"} }
	return cartographer.Board{
		Rows: 3,
		Cols: 4,
		Tiles: []cartographer.Tile{
			{Kind: cartographer.TileStart}, F, P(), F,
			W, W, W, W,
			F, P(), F, {Kind: cartographer.TileExit},
		},
	}
}
