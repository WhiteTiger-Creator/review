package limit

func DecoSlot(grid *BurstGrid) uint32 {
	var total uint32
	for _, cell := range grid.Cells {
		total += cell.Hits
	}
	return total
}
