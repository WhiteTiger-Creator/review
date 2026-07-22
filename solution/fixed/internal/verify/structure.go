package verify

import (
	"encoding/hex"
	"fmt"
	"strconv"
	"strings"

	"beaconaudit/internal/model"
)

func validatePulseStructure(p model.Pulse, origin string) error {
	if p.StatusCode != 0 || p.External.StatusCode != 0 {
		return fmt.Errorf("pulse %d has a nonzero status code", p.PulseIndex)
	}
	for _, field := range []struct {
		name   string
		value  string
		length int
	}{
		{"localRandomValue", p.LocalRandomValue, 64},
		{"external.sourceId", p.External.SourceID, 64},
		{"external.value", p.External.Value, 64},
		{"precommitmentValue", p.PrecommitmentValue, 64},
		{"signatureValue", p.SignatureValue, 512},
		{"outputValue", p.OutputValue, 64},
	} {
		if err := requireUpperHex(field.value, field.length, field.name); err != nil {
			return err
		}
	}
	certificate, err := hex.DecodeString(p.CertificateID)
	if err != nil || len(certificate) != 64 {
		return fmt.Errorf("certificateId must be 64 bytes of hexadecimal")
	}
	if p.CertificateID != strings.ToLower(p.CertificateID) && p.CertificateID != strings.ToUpper(p.CertificateID) {
		return fmt.Errorf("certificateId must use one consistent hexadecimal case")
	}

	required := map[string]bool{"previous": false, "hour": false, "day": false, "month": false, "year": false}
	prefix := fmt.Sprintf("%s/beacon/2.0/chain/%d/pulse/", origin, p.ChainIndex)
	for _, link := range p.ListValues {
		if _, known := required[link.Type]; !known {
			return fmt.Errorf("pulse %d has unexpected %s list value", p.PulseIndex, link.Type)
		}
		if required[link.Type] {
			return fmt.Errorf("pulse %d has duplicate %s list value", p.PulseIndex, link.Type)
		}
		required[link.Type] = true
		if err := requireUpperHex(link.Value, 64, link.Type); err != nil {
			return err
		}
		if !strings.HasPrefix(link.URI, prefix) {
			return fmt.Errorf("pulse %d %s list URI is outside its chain", p.PulseIndex, link.Type)
		}
		linkedIndex, err := strconv.ParseUint(strings.TrimPrefix(link.URI, prefix), 10, 64)
		if err != nil || linkedIndex == 0 || linkedIndex > p.PulseIndex {
			return fmt.Errorf("pulse %d %s list URI is invalid", p.PulseIndex, link.Type)
		}
		if link.Type == "previous" && (p.PulseIndex == 0 || linkedIndex != p.PulseIndex-1) {
			return fmt.Errorf("pulse %d previous list URI is not the preceding pulse", p.PulseIndex)
		}
	}
	for kind, present := range required {
		if !present {
			return fmt.Errorf("pulse %d is missing %s list value", p.PulseIndex, kind)
		}
	}
	return nil
}

func requireUpperHex(value string, length int, label string) error {
	decoded, err := hex.DecodeString(value)
	if err != nil || len(decoded) != length || fmt.Sprintf("%X", decoded) != value {
		return fmt.Errorf("%s must be %d bytes of uppercase hexadecimal", label, length)
	}
	return nil
}
