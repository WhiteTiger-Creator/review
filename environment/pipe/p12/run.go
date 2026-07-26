package p12

import (
	"adreq/a4p"
	"adreq/b7k"
	"adreq/nx"
	"adreq/w3j"
)

// Run resets the tip journal, packs zones, replays freeze weights, and folds regret.
func Run(root string, arm int) (nx.Bundle, error) {
	tip := nx.NewTip(root)
	tip.Reset()

	rows := a4p.Pack(root, 1, arm)
	tip.CommitPack(arm, rows)

	w, freeze := w3j.Replay(root, arm)
	tip.CommitWeights(arm, w, freeze)

	unit := b7k.Fold(rows, w, root, arm)
	tip.CommitRegret(arm, unit)

	return nx.Bundle{
		Rows:    rows,
		Units:   []nx.RgUnit{unit},
		Weights: w,
		Tip:     tip,
	}, nil
}
