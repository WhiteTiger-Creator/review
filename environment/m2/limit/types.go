package limit

type EventRow struct {
	FieldByte uint8
}

type EventBatch struct {
	Rows []EventRow
}

type BurstCell struct {
	ArmID uint8
	Mask  uint16
	Hits  uint32
}

type BurstGrid struct {
	Cells       []BurstCell
	Family      string
	PolicyGen   uint32
	ShadowEpoch uint32
	CacheEpoch  uint32
}

type TallyErr struct{}

func (TallyErr) Error() string { return "tally err" }
