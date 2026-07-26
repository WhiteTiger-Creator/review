package w3j

import (
	"sort"

	"adreq/nx"
)

// wj_r reconstructs freeze-epoch weights by replaying the online-learner journal.
func wj_r(root string, arm int) (nx.Weights, uint32) {
	arms, err := nx.LoadSplit(root)
	if err != nil || arm < 0 || arm >= len(arms) {
		return nx.Weights{}, 0
	}
	fr := arms[arm].FreezeEpoch
	base, err := nx.LoadBaseWeights(root)
	if err != nil {
		return nx.Weights{}, 0
	}
	_, updates, err := nx.LoadJournal(root)
	if err != nil {
		return nx.Weights{}, 0
	}
	sort.SliceStable(updates, func(i, j int) bool {
		return updates[i].Epoch < updates[j].Epoch
	})
	out := nx.CloneWeights(base)
	for _, u := range updates {
		if u.Epoch > fr {
			continue
		}
		for i := 0; i < len(out.W) && i < len(u.DW); i++ {
			out.W[i] += u.DW[i]
		}
		out.B += u.DB
	}
	return out, fr
}

// Replay is the exported stage entry for pipe wiring.
func Replay(root string, arm int) (nx.Weights, uint32) {
	return wj_r(root, arm)
}

func applyUpdate(w nx.Weights, u nx.JournalUpdate) nx.Weights {
	out := nx.CloneWeights(w)
	for i := 0; i < len(out.W) && i < len(u.DW); i++ {
		out.W[i] += u.DW[i]
	}
	out.B += u.DB
	return out
}
