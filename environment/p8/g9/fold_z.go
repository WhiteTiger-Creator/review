package g9

import (
	"os"
	"path/filepath"
	"sort"
	"strconv"

	"stormlab/pol"
)

func fold_z(budget SlotBudget, grid *ScoreGrid, out *OrderSink) error {
	if len(grid.Scores) == 0 {
		return SeekErr{}
	}
	out.LaneOrder = out.LaneOrder[:0]
	take := int(budget.Slots)
	if take > len(grid.Scores) {
		take = len(grid.Scores)
	}
	anchor := readGenBoundAnchor()
	scored := append([]LaneScore(nil), grid.Scores...)
	sort.Slice(scored, func(i, j int) bool {
		if scored[i].Score != scored[j].Score {
			return scored[i].Score > scored[j].Score
		}
		ti := anchor[int(scored[i].ID)%8]
		tj := anchor[int(scored[j].ID)%8]
		if ti != tj {
			return ti < tj
		}
		return scored[i].ID < scored[j].ID
	})
	for i := 0; i < take; i++ {
		out.LaneOrder = append(out.LaneOrder, int(scored[i].ID))
	}
	out.Anchor = anchor
	out.Staging++
	return nil
}

func readGenBoundAnchor() [8]byte {
	gen := pol.ActiveGen()
	cp := filepath.Join("/app/environment/pack/checkpoints", "stg_g"+strconv.Itoa(gen)+".bin")
	if data, err := os.ReadFile(cp); err == nil && len(data) >= 8 {
		var out [8]byte
		copy(out[:], data[:8])
		return out
	}
	return ReadStagedAnchor()
}

func Run(budget SlotBudget, grid *ScoreGrid, out *OrderSink) error {
	return fold_z(budget, grid, out)
}
