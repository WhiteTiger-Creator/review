package folds

import (
	"trustloom/internal/als"
	"trustloom/internal/data"
	"trustloom/internal/rank"
)

const FoldK = 4

type FoldResult struct {
	FoldIndex    int     `json:"fold_index"`
	NTrainUsers  int     `json:"n_train_users"`
	NTrainItems  int     `json:"n_train_items"`
	NTrainPairs  int     `json:"n_train_pairs"`
	EligibleUsers int    `json:"eligible_users"`
	MAPAtK       float64 `json:"map_at_k"`
}

func Evaluate(global *data.Catalog) []FoldResult {
	out := make([]FoldResult, FoldK)
	for f := 0; f < FoldK; f++ {
		train := map[[2]int]int{}
		hold := map[[2]int]int{}
		for key, c := range global.Pairs {
			ui := global.UserIdx[key[0]]
			ii := global.ItemIdx[key[1]]
			bucket := (2*ui + 3*ii) % FoldK
			if bucket == f {
				hold[key] = c
			} else {
				train[key] = c
			}
		}
		train = data.Remass(train)
		cat := data.FromPairs(train)
		model := als.Fit(cat)
		relevant := map[int]map[int]bool{}
		for key := range hold {
			u, i := key[0], key[1]
			if _, okU := cat.UserIdx[u]; !okU {
				continue
			}
			if _, okI := cat.ItemIdx[i]; !okI {
				continue
			}
			if relevant[u] == nil {
				relevant[u] = map[int]bool{}
			}
			relevant[u][i] = true
		}
		m, e := rank.MAPOnly(model, cat, relevant)
		out[f] = FoldResult{
			FoldIndex:     f,
			NTrainUsers:   len(cat.Users),
			NTrainItems:   len(cat.Items),
			NTrainPairs:   cat.NPairs,
			EligibleUsers: e,
			MAPAtK:        m,
		}
	}
	return out
}
