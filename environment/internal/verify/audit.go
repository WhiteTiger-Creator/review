package verify

import (
	"fmt"
	"strings"

	"beaconaudit/internal/model"
)

func Audit(item model.Case, policy model.Policy, trust model.Trust, directory string) (model.Receipt, error) {
	evidence, certificate, err := LoadEvidence(item, directory)
	if err != nil {
		return model.Receipt{}, err
	}
	if len(evidence) == 0 {
		return model.Receipt{}, fmt.Errorf("evidence interval is empty")
	}
	certificateID := evidence[0].Pulse.CertificateID
	if err := CheckTrust(certificate, certificateID, trust); err != nil {
		return model.Receipt{}, err
	}
	results := make([]model.PulseResult, 0, len(evidence))
	for offset, itemEvidence := range evidence {
		expected := item.FirstPulse + uint64(offset)
		if itemEvidence.Pulse.PulseIndex != expected {
			return model.Receipt{}, fmt.Errorf("evidence filename/index mismatch at %d", expected)
		}
		if itemEvidence.Pulse.CertificateID != certificateID {
			return model.Receipt{}, fmt.Errorf("certificate changed inside interval")
		}
		result, checkErr := CheckPulse(item, policy, certificate, itemEvidence)
		if checkErr != nil {
			return model.Receipt{}, checkErr
		}
		results = append(results, result)
	}
	continuity, err := CheckContinuity(evidence, policy)
	if err != nil {
		return model.Receipt{}, err
	}
	return model.Receipt{
		CaseID: item.CaseID, APIOrigin: item.APIOrigin, ChainIndex: item.ChainIndex,
		FirstPulse: item.FirstPulse, LastPulse: item.LastPulse,
		CertificateID: strings.ToUpper(certificateID), CertificateSHA512: certificate.Fingerprint,
		PolicyProfile: policy.Profile, TrustProfile: trust.TrustProfile, Pulses: results,
		Continuity: continuity, AuditedAt: results[len(results)-1].Timestamp, Result: "PASS",
	}, nil
}
