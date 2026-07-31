package planner

func (ctx context) eligible(mask, completed uint16) bool {
	for index := range ctx.targets {
		bit := uint16(1) << index
		if mask&bit == 0 {
			continue
		}
		if ctx.predecessors[index]&completed != ctx.predecessors[index] {
			return false
		}
	}
	return true
}
