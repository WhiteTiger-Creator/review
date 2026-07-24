package w3j

// Frame is one sealed journal record after per-arm normalize.
type Frame struct {
	Pkg    string `json:"pkg"`
	Dep    string `json:"dep"`
	Lo     string `json:"lo"`
	Hi     string `json:"hi"`
	PreTok string `json:"pre_tok"`
	Lift   bool   `json:"lift"`
	ActTok string `json:"act_tok"`
	Seq    int    `json:"seq"`
	ArmTag byte   `json:"arm_tag"`
	Epoch  uint64 `json:"epoch"`
	CRC    string `json:"crc"`
}

type RawLine struct {
	Bytes  []byte
	ArmTag byte
}
