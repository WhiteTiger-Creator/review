package planner

func (ctx context) validWave(mask uint16) bool {
	if mask == 0 || bitCount(mask) > ctx.policy.MaxWaveSize {
		return false
	}
	zones := map[string]int{}
	racks := map[string]int{}
	unavailable := map[string]int{}
	for index, id := range ctx.targets {
		if mask&(uint16(1)<<index) == 0 {
			continue
		}
		node := ctx.nodes[id]
		zones[node.Zone]++
		racks[node.Rack] += node.Power
		for _, service := range node.Services {
			unavailable[service]++
		}
	}
	for zone, count := range zones {
		if count > ctx.policy.ZoneParallel[zone] {
			return false
		}
	}
	for rack, power := range racks {
		if power > ctx.policy.RackPowerLimit[rack] {
			return false
		}
	}
	for service, minimum := range ctx.policy.MinAvailable {
		if ctx.serviceTotal[service]-unavailable[service] < minimum {
			return false
		}
	}
	return true
}
