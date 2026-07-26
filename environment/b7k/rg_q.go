package b7k

import "adreq/nx"

// rg_q folds rows; broken path ignores provided freeze weights and uses tip.
func rg_q(rows []nx.ZnRow, w nx.Weights, root string, arm int) nx.RgUnit {
	return rg_diag(rows, w, root, arm)
}

// Fold is the exported stage entry for pipe wiring.
func Fold(rows []nx.ZnRow, w nx.Weights, root string, arm int) nx.RgUnit {
	return rg_q(rows, w, root, arm)
}
