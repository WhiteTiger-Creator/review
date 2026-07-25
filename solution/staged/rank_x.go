package graph

import (
	"sort"

	"stormlab/pol"
)

func rank_x(arms *EdgeArms, sink *ShadowSink) error {
	if len(arms.Items) == 0 {
		return ChainErr{}
	}
	sink.Active = sink.Active[:0]
	sink.Suppressed = make(map[uint8]struct{})
	radius := pol.ActiveRadius()
	order := append([]EdgeArm(nil), arms.Items...)
	sort.Slice(order, func(i, j int) bool { return order[i].Seq < order[j].Seq })
	for _, arm := range order {
		if arm.Kind != ArmExclude || arm.ShadowLink == 0 {
			continue
		}
		link := arm.ShadowLink
		for _, other := range arms.Items {
			if other.Kind != ArmInclude {
				continue
			}
			if (other.Mask & arm.Mask) == 0 {
				continue
			}
			diff := int(other.ID)
			if diff > int(link) {
				diff -= int(link)
			} else {
				diff = int(link) - diff
			}
			if diff >= radius {
				sink.Suppressed[other.ID] = struct{}{}
			}
		}
	}
	for _, arm := range order {
		if arm.Kind == ArmInclude {
			if _, blocked := sink.Suppressed[arm.ID]; !blocked {
				sink.Active = append(sink.Active, arm.ID)
			}
		}
	}
	sink.Epoch++
	return nil
}

func Run(arms *EdgeArms, sink *ShadowSink) error {
	return rank_x(arms, sink)
}
