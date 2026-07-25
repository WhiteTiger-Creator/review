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
	type row struct {
		id    uint8
		score uint32
		tie   uint8
	}
	scored := make([]row, len(grid.Scores))
	for i, s := range grid.Scores {
		scored[i] = row{id: s.ID, score: s.Score, tie: anchor[int(s.ID)%8]}
	}
	sort.Slice(scored, func(i, j int) bool {
		if scored[i].score != scored[j].score {
			return scored[i].score > scored[j].score
		}
		if scored[i].tie != scored[j].tie {
			return scored[i].tie > scored[j].tie
		}
		return scored[i].id < scored[j].id
	})
	for i := 0; i < take; i++ {
		out.LaneOrder = append(out.LaneOrder, int(scored[i].id))
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
