package verify

import (
	"crypto/x509"
	"fmt"
	"strings"

	"beaconaudit/internal/cryptoutil"
	"beaconaudit/internal/model"
)

func CheckTrust(certificate cryptoutil.Certificate, identifier string, trust model.Trust) error {
	wanted := strings.ToUpper(identifier)
	if certificate.Fingerprint != wanted {
		return fmt.Errorf("certificate SHA-512 does not match pulse certificateId")
	}
	trusted := false
	for _, allowed := range trust.AllowedCertificateIDs {
		if strings.ToUpper(allowed) == wanted {
			trusted = true
		}
	}
	if !trusted {
		return fmt.Errorf("certificateId is not present in trust profile")
	}
	if certificate.Parsed.Subject.CommonName != trust.ExpectedSubjectCommonName {
		return fmt.Errorf("certificate subject common name is not trusted")
	}
	if err := certificate.Parsed.VerifyHostname(trust.ExpectedSubjectCommonName); err != nil {
		return fmt.Errorf("certificate subject alternative name is not trusted")
	}
	if certificate.Parsed.IsCA || certificate.Parsed.KeyUsage&x509.KeyUsageDigitalSignature == 0 {
		return fmt.Errorf("certificate is not an end-entity digital-signature certificate")
	}
	if certificate.PublicKey.E != 65537 {
		return fmt.Errorf("certificate RSA exponent is not 65537")
	}
	return nil
}
