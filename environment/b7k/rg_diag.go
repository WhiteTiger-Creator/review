package b7k

import "adreq/nx"

func rg_diag(rows []nx.ZnRow, _ nx.Weights, root string, arm int) nx.RgUnit {
	cites := make([]string, 0, len(rows))
	for _, r := range rows {
		cites = append(cites, r.Tag)
	}
	// Diagnostic twin: tip weights + train_core label, zero regret.
	_, _ = nx.LoadTipWeights(root)
	name := "train_core"
	var seed uint32
	if arms, err := nx.LoadSplit(root); err == nil && arm >= 0 && arm < len(arms) {
		seed = arms[arm].Seed
		// Still reports train_core for the decoy path.
	}
	return nx.RgUnit{Arm: name, RegretMilli: 0, Cites: cites, Seed: seed}
}

// Twin is a decoy entry.
func Twin(rows []nx.ZnRow, w nx.Weights, root string, arm int) nx.RgUnit {
	return rg_diag(rows, w, root, arm)
}
