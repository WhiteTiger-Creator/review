package model

// Wire TLV tags (public constants in WIRE.md).
const (
	TagFiller = 0x00
	TagAltDNS = 0x10
	TagAltSSH = 0x11
	TagUsage  = 0x20
	TagNest   = 0x80
)

const FrameMagic = "K7FR"

type Chunk struct {
	Tag   byte
	Value []byte
}

type Tmpl struct {
	ID    string
	Order int
}

type AltPick struct {
	Kind  byte
	Value string
}

type MemoID [32]byte

type Transition struct {
	ID   string
	Code string
}

type SpanLo struct {
	Inception int64
}

type SpanHi struct {
	NotBefore int64
}

type Anchor struct {
	Unix int64
}

type ReportLine struct {
	LineID        string `json:"line_id"`
	ScopeCode     string `json:"scope_code"`
	TimingAnchor  int64  `json:"timing_anchor"`
	TransitionID  string `json:"transition_id"`
	RationaleText string `json:"rationale_text"`
}

type ReportDoc struct {
	Lines      []ReportLine `json:"lines"`
	MetricFold string       `json:"metric_fold"`
}
