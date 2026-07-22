package verify

import (
	"fmt"
	"time"

	"beaconaudit/internal/cryptoutil"
	"beaconaudit/internal/model"
)

func CheckPulse(item model.Case, policy model.Policy, cert cryptoutil.Certificate, evidence EvidencePulse) (model.PulseResult, error) {
	p := evidence.Pulse
	expectedURI := fmt.Sprintf("%s/beacon/2.0/chain/%d/pulse/%d", item.APIOrigin, item.ChainIndex, p.PulseIndex)
	if p.URI != expectedURI || p.ChainIndex != item.ChainIndex {
		return model.PulseResult{}, fmt.Errorf("pulse %d source identity mismatch", p.PulseIndex)
	}
	if p.Version != policy.Version || p.CipherSuite != policy.CipherSuite || p.Period != policy.PeriodMS {
		return model.PulseResult{}, fmt.Errorf("pulse %d violates cipher/version/period policy", p.PulseIndex)
	}
	when, err := time.Parse("2006-01-02T15:04:05.000Z", p.TimeStamp)
	if err != nil {
		return model.PulseResult{}, fmt.Errorf("pulse %d timestamp is not canonical UTC", p.PulseIndex)
	}
	validAtPulse := !when.Before(cert.Parsed.NotBefore) && !when.After(cert.Parsed.NotAfter)
	if policy.RequireCertificateTimeValidity && !validAtPulse {
		return model.PulseResult{}, fmt.Errorf("certificate was not valid at pulse %d timestamp", p.PulseIndex)
	}
	if policy.RequireSignatures {
		if err := cryptoutil.VerifyPulseSignature(p, cert.PublicKey); err != nil {
			return model.PulseResult{}, err
		}
	}
	if policy.RequireOutputHashes {
		if err := cryptoutil.VerifyOutputHash(p); err != nil {
			return model.PulseResult{}, err
		}
	}
	return model.PulseResult{
		Index: p.PulseIndex, Timestamp: p.TimeStamp, SourceURI: p.URI,
		EvidenceFile: evidence.Filename, EvidenceSHA512: evidence.RawSHA512,
		OutputValue: p.OutputValue, SignatureVerified: true, OutputHashVerified: true,
		CertificateValidAtPulse: validAtPulse,
	}, nil
}
