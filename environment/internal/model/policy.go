package model

type Policy struct {
	Profile                        string `json:"profile"`
	Version                        string `json:"version"`
	CipherSuite                    uint32 `json:"cipher_suite"`
	PeriodMS                       uint32 `json:"period_ms"`
	RequireCertificateTimeValidity bool   `json:"require_certificate_time_validity"`
	RequireSignatures              bool   `json:"require_signatures"`
	RequireOutputHashes            bool   `json:"require_output_hashes"`
	RequirePreviousLinks           bool   `json:"require_previous_links"`
	RequirePrecommitments          bool   `json:"require_precommitments"`
}

type Trust struct {
	TrustProfile              string   `json:"trust_profile"`
	AllowedCertificateIDs     []string `json:"allowed_certificate_ids"`
	ExpectedSubjectCommonName string   `json:"expected_subject_common_name"`
}
