package b7k

import (
	"math"

	"adreq/nx"
)

// rg_q folds packed rows through freeze-epoch online-learner regret inference.
func rg_q(rows []nx.ZnRow, w nx.Weights, root string, arm int) nx.RgUnit {
	arms, err := nx.LoadSplit(root)
	if err != nil || arm < 0 || arm >= len(arms) {
		return nx.RgUnit{}
	}
	sa := arms[arm]
	var learn, bestPos, bestNeg float64
	cites := make([]string, 0, len(rows))
	for _, r := range rows {
		cites = append(cites, r.Tag)
		score := nx.Dot(w.W, r.Feats, w.B)
		learn += nx.Hinge(r.Lab, score)
		bestPos += nx.Hinge(r.Lab, 1)
		bestNeg += nx.Hinge(r.Lab, -1)
	}
	best := bestPos
	if bestNeg < best {
		best = bestNeg
	}
	n := len(rows)
	if n == 0 {
		n = 1
	}
	r := (learn - best) / float64(n)
	milli := int64(math.Round(1000 * r))
	if milli < 0 {
		milli = 0
	}
	return nx.RgUnit{
		Arm:         sa.Name,
		RegretMilli: milli,
		Cites:       cites,
		Seed:        sa.Seed,
		FreezeEpoch: sa.FreezeEpoch,
	}
}

// Fold is the exported stage entry for pipe wiring.
func Fold(rows []nx.ZnRow, w nx.Weights, root string, arm int) nx.RgUnit {
	return rg_q(rows, w, root, arm)
}

func milliOf(learn, best float64, n int) int64 {
	if n <= 0 {
		n = 1
	}
	r := (learn - best) / float64(n)
	v := int64(math.Round(1000 * r))
	if v < 0 {
		return 0
	}
	return v
}
