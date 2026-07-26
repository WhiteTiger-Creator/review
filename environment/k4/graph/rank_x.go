package graph

func rank_x(arms *EdgeArms, sink *ShadowSink) error {
	if len(arms.Items) == 0 {
		return ChainErr{}
	}
	sink.Active = sink.Active[:0]
	sink.Suppressed = make(map[uint8]struct{})
	radius := 1
	for _, arm := range arms.Items {
		if arm.Kind == ArmExclude && arm.ShadowLink != 0 {
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
