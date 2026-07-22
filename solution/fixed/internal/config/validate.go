package config

import (
	"encoding/hex"
	"fmt"
	"math"
	"strconv"

	"beaconaudit/internal/model"
)

func ValidateCase(item model.Case) error {
	if item.APIOrigin != "https://beacon.nist.gov" {
		return fmt.Errorf("case api_origin must be https://beacon.nist.gov")
	}
	if item.CaseID == "" || item.ChainIndex == 0 || item.FirstPulse == 0 || item.LastPulse < item.FirstPulse {
		return fmt.Errorf("case interval is invalid")
	}
	if item.LastPulse-item.FirstPulse > 100 {
		return fmt.Errorf("case interval exceeds acquisition limit")
	}
	if item.LastPulse == math.MaxUint64 {
		return fmt.Errorf("case interval cannot end at the uint64 limit")
	}
	if item.PolicyPath == "" || item.TrustPath == "" {
		return fmt.Errorf("case policy and trust paths are required")
	}
	if len(item.PulseSHA512) != int(item.LastPulse-item.FirstPulse+1) {
		return fmt.Errorf("case must pin one SHA-512 digest per pulse")
	}
	for index := item.FirstPulse; index <= item.LastPulse; index++ {
		if err := validateSHA512(item.PulseSHA512[strconv.FormatUint(index, 10)]); err != nil {
			return fmt.Errorf("case pulse %d SHA-512 pin is invalid", index)
		}
	}
	if err := validateSHA512(item.CertificateSHA512); err != nil {
		return fmt.Errorf("case certificate SHA-512 pin is invalid")
	}
	return nil
}

func ValidatePolicy(policy model.Policy) error {
	if policy.Profile != "nist-v2-strict" || policy.Version != "Version 2.0" ||
		policy.CipherSuite != 0 || policy.PeriodMS == 0 {
		return fmt.Errorf("policy is not the supported NIST Beacon 2.0 strict profile")
	}
	if !policy.RequireCertificateTimeValidity || !policy.RequireSignatures ||
		!policy.RequireOutputHashes || !policy.RequirePreviousLinks ||
		!policy.RequirePrecommitments {
		return fmt.Errorf("strict policy cannot disable a required verification")
	}
	return nil
}

func ValidateTrust(trust model.Trust) error {
	if trust.TrustProfile == "" || trust.ExpectedSubjectCommonName == "" || len(trust.AllowedCertificateIDs) == 0 {
		return fmt.Errorf("trust profile is incomplete")
	}
	seen := make(map[string]struct{}, len(trust.AllowedCertificateIDs))
	for _, identifier := range trust.AllowedCertificateIDs {
		decoded, err := hex.DecodeString(identifier)
		if err != nil || len(decoded) != 64 || fmt.Sprintf("%X", decoded) != identifier {
			return fmt.Errorf("trust certificate identifiers must be unique uppercase SHA-512 values")
		}
		if _, duplicate := seen[identifier]; duplicate {
			return fmt.Errorf("trust certificate identifiers must be unique uppercase SHA-512 values")
		}
		seen[identifier] = struct{}{}
	}
	return nil
}

func validateSHA512(value string) error {
	decoded, err := hex.DecodeString(value)
	if err != nil || len(decoded) != 64 || fmt.Sprintf("%X", decoded) != value {
		return fmt.Errorf("not canonical SHA-512")
	}
	return nil
}
