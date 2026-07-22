package y4f

type RowOut struct {
	Pkg       string `json:"pkg"`
	Dep       string `json:"dep"`
	Lo        string `json:"lo"`
	Hi        string `json:"hi"`
	PreTok    string `json:"pre_tok"`
	Lift      bool   `json:"lift"`
	RowDigest string `json:"row_digest"`
}

type ProbeView struct {
	PeerHi map[string]string
}
