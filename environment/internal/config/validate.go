package config

import (
	"fmt"
	"net/url"

	"beaconaudit/internal/model"
)

func ValidateCase(item model.Case) error {
	origin, err := url.Parse(item.APIOrigin)
	if err != nil || origin.Scheme != "https" || origin.Host != "beacon.nist.gov" || origin.Path != "" {
		return fmt.Errorf("case api_origin must be https://beacon.nist.gov")
	}
	if item.CaseID == "" || item.ChainIndex == 0 || item.FirstPulse == 0 || item.LastPulse < item.FirstPulse {
		return fmt.Errorf("case interval is invalid")
	}
	if item.LastPulse-item.FirstPulse > 100 {
		return fmt.Errorf("case interval exceeds acquisition limit")
	}
	if item.PolicyPath == "" || item.TrustPath == "" {
		return fmt.Errorf("case policy and trust paths are required")
	}
	return nil
}
