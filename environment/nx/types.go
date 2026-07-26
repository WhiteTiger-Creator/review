package nx

// ZnRow is one packed zone row with an opaque tag.
type ZnRow struct {
	Zone  uint16
	Part  uint16
	Tag   string
	Feats []float64
	Lab   int16
}

// RgUnit holds folded regret state for one evaluation arm.
type RgUnit struct {
	Arm         string
	RegretMilli int64
	Cites       []string
	Seed        uint32
	FreezeEpoch uint32
}

// Lane is one metamorphic or fuzz arm descriptor.
type Lane struct {
	Name string
	Kind string
	Arm  string
	Seed uint32
	N    int
}

// MtDigest is a metamorphic-noninterference digest for one lane.
type MtDigest struct {
	Name string
	Hex  string
}

// Weights holds a reconstructed online-learner checkpoint.
type Weights struct {
	W []float64
	B float64
}

// SplitArm is one pinned evaluation arm with a freeze epoch.
type SplitArm struct {
	Name        string
	Hold        bool
	Seed        uint32
	FreezeEpoch uint32
}

// Bundle is the pipe handoff between stages.
type Bundle struct {
	Rows    []ZnRow
	Units   []RgUnit
	Weights Weights
	Digests []MtDigest
	Tip     *TipJournal
}
