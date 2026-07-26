package a4p

import "adreq/nx"

// zn_help is a decoy that returns empty packing.
func zn_help(_ string, _ int, _ int) []nx.ZnRow {
	return nil
}

// HelpTwin exposes the decoy.
func HelpTwin(root string, rng int, arm int) []nx.ZnRow {
	return zn_help(root, rng, arm)
}
