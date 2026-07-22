package model

type Receipt struct {
	CaseID            string            `json:"case_id"`
	APIOrigin         string            `json:"api_origin"`
	ChainIndex        uint64            `json:"chain_index"`
	FirstPulse        uint64            `json:"first_pulse"`
	LastPulse         uint64            `json:"last_pulse"`
	CertificateID     string            `json:"certificate_id"`
	CertificateSHA512 string            `json:"certificate_sha512"`
	PolicyProfile     string            `json:"policy_profile"`
	TrustProfile      string            `json:"trust_profile"`
	Pulses            []PulseResult     `json:"pulses"`
	Continuity        ContinuityResults `json:"continuity"`
	AuditedAt         string            `json:"audited_at"`
	Result            string            `json:"result"`
}

type PulseResult struct {
	Index                   uint64 `json:"index"`
	Timestamp               string `json:"timestamp"`
	SourceURI               string `json:"source_uri"`
	EvidenceFile            string `json:"evidence_file"`
	EvidenceSHA512          string `json:"evidence_sha512"`
	OutputValue             string `json:"output_value"`
	SignatureVerified       bool   `json:"signature_verified"`
	OutputHashVerified      bool   `json:"output_hash_verified"`
	CertificateValidAtPulse bool   `json:"certificate_valid_at_pulse"`
}

type ContinuityResults struct {
	IndexesConsecutive     bool `json:"indexes_consecutive"`
	TimestampsConsecutive  bool `json:"timestamps_consecutive"`
	PreviousLinksVerified  bool `json:"previous_links_verified"`
	PrecommitmentsVerified bool `json:"precommitments_verified"`
}
