package graph

type ArmKind int

const (
	ArmInclude ArmKind = 1
	ArmExclude ArmKind = 2
)

type EdgeArm struct {
	ID         uint8
	Kind       ArmKind
	Mask       uint16
	ShadowLink uint8
	Seq        uint8
}

type EdgeArms struct {
	Items   []EdgeArm
	Permute bool
}

type ShadowSink struct {
	Active     []uint8
	Suppressed map[uint8]struct{}
	Epoch      uint32
}

type ChainErr struct{}

func (ChainErr) Error() string { return "chain err" }
