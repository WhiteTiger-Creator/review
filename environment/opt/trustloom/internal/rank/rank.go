package rank

import (
	"math"
	"sort"
	"trustloom/internal/als"
	"trustloom/internal/data"
)

const K = 3

type Metrics struct {
	PrecisionAtK  float64
	MAPAtK        float64
	NDCGAtK       float64
	EligibleUsers int
}

func Evaluate(m *als.Model, cat *data.Catalog, hold []data.HoldRow) Metrics {
	byUser := map[int][]data.HoldRow{}
	for _, h := range hold {
		byUser[h.User] = append(byUser[h.User], h)
	}
	userIDs := make([]int, 0, len(byUser))
	for u := range byUser {
		userIDs = append(userIDs, u)
	}
	sort.Ints(userIDs)

	var hitTotal, considered int
	var apSumAll, ndcgSumAll float64
	eligible := 0
	for _, u := range userIDs {
		if _, ok := cat.UserIdx[u]; !ok {
			continue
		}
		R := map[int]bool{}
		for _, h := range byUser[u] {
			if h.Label == 1 {
				if _, ok := cat.ItemIdx[h.Item]; ok {
					R[h.Item] = true
				}
			}
		}
		if len(R) == 0 {
			continue
		}
		eligible++
		top := topK(m, cat, u, K)
		hits := 0
		apSum := 0.0
		hitCount := 0
		dcg := 0.0
		for rank, id := range top {
			rel := 0.0
			if R[id] {
				rel = 1.0
				hits++
				hitCount++
				apSum += float64(hitCount) / float64(rank+1)
			}
			dcg += rel / math.Log2(float64(rank+1)+1.0)
		}
		hitTotal += hits
		considered += K
		if hitCount > 0 {
			apSumAll += apSum / float64(hitCount)
		}
		ideal := K
		if len(R) < ideal {
			ideal = len(R)
		}
		idcg := 0.0
		for rank := 1; rank <= ideal; rank++ {
			idcg += 1.0 / math.Log2(float64(rank)+1.0)
		}
		if idcg > 0 {
			ndcgSumAll += dcg / idcg
		}
	}
	if eligible == 0 || considered == 0 {
		return Metrics{}
	}
	return Metrics{
		PrecisionAtK:  float64(hitTotal) / float64(considered),
		MAPAtK:        apSumAll / float64(eligible),
		NDCGAtK:       ndcgSumAll / float64(eligible),
		EligibleUsers: eligible,
	}
}

func MAPOnly(m *als.Model, cat *data.Catalog, relevant map[int]map[int]bool) (float64, int) {
	// lab stub: always 0
	return 0, 0
}

func topK(m *als.Model, cat *data.Catalog, userID, k int) []int {
	type scored struct {
		id    int
		score float64
	}
	scoredItems := make([]scored, 0, len(cat.Items))
	for _, iid := range cat.Items {
		scoredItems = append(scoredItems, scored{id: iid, score: m.Score(cat, userID, iid)})
	}
	sort.Slice(scoredItems, func(i, j int) bool {
		if scoredItems[i].score == scoredItems[j].score {
			return scoredItems[i].id > scoredItems[j].id
		}
		return scoredItems[i].score > scoredItems[j].score
	})
	if len(scoredItems) > k {
		scoredItems = scoredItems[:k]
	}
	out := make([]int, len(scoredItems))
	for i, s := range scoredItems {
		out[i] = s.id
	}
	return out
}
