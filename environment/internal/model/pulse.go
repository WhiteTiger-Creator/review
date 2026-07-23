package model

type PulseEnvelope struct {
	Pulse Pulse `json:"pulse"`
}

type Pulse struct {
	URI                string      `json:"uri"`
	Version            string      `json:"version"`
	CipherSuite        uint32      `json:"cipherSuite"`
	Period             uint32      `json:"period"`
	CertificateID      string      `json:"certificateId"`
	ChainIndex         uint64      `json:"chainIndex"`
	PulseIndex         uint64      `json:"pulseIndex"`
	TimeStamp          string      `json:"timeStamp"`
	LocalRandomValue   string      `json:"localRandomValue"`
	External           External    `json:"external"`
	ListValues         []ListValue `json:"listValues"`
	PrecommitmentValue string      `json:"precommitmentValue"`
	StatusCode         uint32      `json:"statusCode"`
	SignatureValue     string      `json:"signatureValue"`
	OutputValue        string      `json:"outputValue"`
}

type External struct {
	SourceID   string `json:"sourceId"`
	StatusCode uint32 `json:"statusCode"`
	Value      string `json:"value"`
}

type ListValue struct {
	URI   string `json:"uri"`
	Type  string `json:"type"`
	Value string `json:"value"`
}

func (p Pulse) Link(kind string) (string, bool) {
	for _, value := range p.ListValues {
		if value.Type == kind {
			return value.Value, true
		}
	}
	return "", false
}
