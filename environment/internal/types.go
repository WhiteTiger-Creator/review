package internal

// RowTag is one scored pack row under an arm index.
type RowTag struct {
	Ix    uint16
	Role  uint8
	Score float64
	Tag   string
	Ka    int
	Kb    int
	Lim   int
}

// LatticeUnit is a folded effect unit with role-gated counts.
type LatticeUnit struct {
	Hex     string
	Ka      int
	Kb      int
	Lim     int
	Tags    []string
	WTags   []string
	CiteTag string
	Seal    string
	Arm     string
	PackFP  string
}

// JumpArm is one discontinuity arm record.
type JumpArm struct {
	Name   string
	Kind   string
	Seed   uint64
	Jump   int
	Rotate int
}

// JumpDigest binds a rebound unit under one arm.
type JumpDigest struct {
	Hex      string
	Arm      string
	Seed     uint64
	Rotate   int
	Ka       int
	Kb       int
	Lim      int
	LatHex   string
	ScoreTag string
	UnitKey  string
	Cite     string
}

// ProofDigest names the emitted proof artifact.
type ProofDigest struct {
	Hex  string
	Path string
}
