package graph

import "sort"

func DecoRank(arms *EdgeArms) []uint8 {
	order := append([]EdgeArm(nil), arms.Items...)
	sort.Slice(order, func(i, j int) bool { return order[i].Seq < order[j].Seq })
	out := make([]uint8, 0, len(order))
	for _, arm := range order {
		if arm.Kind == ArmInclude {
			out = append(out, arm.ID)
		}
	}
	return out
}
