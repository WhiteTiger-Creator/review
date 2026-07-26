package limit

import "sync"

type cacheEntry struct {
	family      string
	policyGen   uint32
	cellLen     int
	eventLen    int
	shadowEpoch uint32
	eventSig    uint64
	hits        []uint32
}

var hitCache sync.Mutex
var cached *cacheEntry

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
	sig := eventSignature(events)
	hitCache.Lock()
	defer hitCache.Unlock()
	if cached != nil &&
		cached.family == windows.Family &&
		cached.policyGen == windows.PolicyGen &&
		cached.cellLen == len(windows.Cells) &&
		cached.eventLen == len(events.Rows) &&
		cached.shadowEpoch == windows.ShadowEpoch &&
		cached.eventSig == sig {
		for i, cell := range windows.Cells {
			cell.Hits = cached.hits[i]
			windows.Cells[i] = cell
		}
		windows.CacheEpoch = windows.ShadowEpoch
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
	cached = &cacheEntry{
		family:      windows.Family,
		policyGen:   windows.PolicyGen,
		cellLen:     len(windows.Cells),
		eventLen:    len(events.Rows),
		shadowEpoch: windows.ShadowEpoch,
		eventSig:    sig,
		hits:        hits,
	}
	windows.CacheEpoch = windows.ShadowEpoch
	return nil
}

func Run(windows *BurstGrid, events *EventBatch) error {
	return slot_y(windows, events)
}
