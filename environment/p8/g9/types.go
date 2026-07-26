package g9

type SlotBudget struct {
	Slots uint8
}

type LaneScore struct {
	ID    uint8
	Score uint32
}

type ScoreGrid struct {
	Scores []LaneScore
}

type OrderSink struct {
	LaneOrder []int
	Anchor    [8]byte
	Staging   uint32
}

type SeekErr struct{}

func (SeekErr) Error() string { return "seek err" }
