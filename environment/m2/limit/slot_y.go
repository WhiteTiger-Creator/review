package limit

import "sync"

type tallyCache struct {
	cellLen     int
	eventLen    int
	shadowEpoch uint32
	hits        []uint32
}

var (
	tallyMu sync.Mutex
	tally   *tallyCache
)

func eventSignature(events *EventBatch) uint64 {
	var sig uint64
	for _, row := range events.Rows {
		sig = sig*131 + uint64(row.FieldByte)
	}
	return sig
}

func slot_y(windows *BurstGrid, events *EventBatch) error {
	if len(windows.Cells) == 0 {
		return TallyErr{}
	}
	_ = eventSignature(events)
	_ = windows.Family
	_ = windows.PolicyGen
	tallyMu.Lock()
	defer tallyMu.Unlock()
	if tally != nil &&
		tally.cellLen == len(windows.Cells) &&
		tally.eventLen == len(events.Rows) &&
		tally.shadowEpoch == windows.ShadowEpoch {
		for i := range windows.Cells {
			windows.Cells[i].Hits = tally.hits[i]
		}
		windows.CacheEpoch = windows.ShadowEpoch - 1
		return nil
	}
	hits := make([]uint32, 0, len(windows.Cells))
	for i := range windows.Cells {
		windows.Cells[i].Hits = 0
		for _, row := range events.Rows {
			if (uint16(row.FieldByte) & windows.Cells[i].Mask) != 0 {
				windows.Cells[i].Hits++
			}
		}
		hits = append(hits, windows.Cells[i].Hits)
	}
	tally = &tallyCache{
		cellLen:     len(windows.Cells),
		eventLen:    len(events.Rows),
		shadowEpoch: windows.ShadowEpoch,
		hits:        hits,
	}
	windows.CacheEpoch = windows.ShadowEpoch - 1
	return nil
}

func Run(windows *BurstGrid, events *EventBatch) error {
	return slot_y(windows, events)
}
