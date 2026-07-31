package planner

import (
	"racklight/drainwave/internal/model"
)

// Plan keeps maintenance predictable by filling each wave in node-name order.
func Plan(inventory model.Inventory, policy model.Policy) ([][]string, bool) {
	ctx := newContext(inventory, policy)
	completed := uint16(0)
	all := (uint16(1) << len(ctx.targets)) - 1
	waves := [][]string{}
	for completed != all {
		wave := uint16(0)
		for index := range ctx.targets {
			bit := uint16(1) << index
			if completed&bit != 0 || !ctx.eligible(bit, completed) {
				continue
			}
			candidate := wave | bit
			if ctx.eligible(candidate, completed) && ctx.validWave(candidate) {
				wave = candidate
			}
		}
		if wave == 0 {
			return nil, false
		}
		waves = append(waves, ctx.names(wave))
		completed |= wave
	}
	return waves, true
}
