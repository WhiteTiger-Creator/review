package model

type Case struct {
	CaseID            string            `json:"case_id"`
	APIOrigin         string            `json:"api_origin"`
	ChainIndex        uint64            `json:"chain_index"`
	FirstPulse        uint64            `json:"first_pulse"`
	LastPulse         uint64            `json:"last_pulse"`
	PolicyPath        string            `json:"policy"`
	TrustPath         string            `json:"trust"`
	PulseSHA512       map[string]string `json:"pulse_sha512"`
	CertificateSHA512 string            `json:"certificate_sha512"`
}
