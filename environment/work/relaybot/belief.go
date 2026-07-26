package main

// Belief helpers track last known enemy placements from observations.
// The starter bot only uses them lightly; the oracle replaces this file.

func visibleSet(squares []string) map[string]bool {
	m := map[string]bool{}
	for _, s := range squares {
		m[s] = true
	}
	return m
}

func ownKingSquare(pieces []PieceView, side string) string {
	for _, p := range pieces {
		if p.Own && p.Kind == "k" {
			return p.Square
		}
	}
	return ""
}
