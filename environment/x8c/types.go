package x8c

import "depctrl/w3j"

type Edge struct {
	ID         string `json:"id"`
	Pkg        string `json:"pkg"`
	Dep        string `json:"dep"`
	Lo         string `json:"lo"`
	Hi         string `json:"hi"`
	Optional   bool   `json:"optional"`
	ActKey     string `json:"act_key"`
	ActPresent bool   `json:"act_present"`
}

type GraphView struct {
	Edges []Edge
}

type Decision struct {
	Hit     bool
	KeyHex  string
	RowsRaw []byte
	Edges   []Edge
}

type Material struct {
	SeedJSON   []byte
	ActJSON    []byte
	Frames     []w3j.Frame
	PeerFinger string
}
