package cryptoutil

import (
	"crypto/rsa"
	"crypto/x509"
	"encoding/pem"
	"fmt"

	"beaconaudit/internal/codec"
)

type Certificate struct {
	Parsed      *x509.Certificate
	PublicKey   *rsa.PublicKey
	Fingerprint string
}

func ParseCertificate(data []byte) (Certificate, error) {
	block, rest := pem.Decode(data)
	if block == nil || block.Type != "CERTIFICATE" || len(rest) != 0 {
		return Certificate{}, fmt.Errorf("certificate response must contain exactly one PEM certificate")
	}
	parsed, err := x509.ParseCertificate(block.Bytes)
	if err != nil {
		return Certificate{}, fmt.Errorf("parse certificate: %w", err)
	}
	publicKey, ok := parsed.PublicKey.(*rsa.PublicKey)
	if !ok {
		return Certificate{}, fmt.Errorf("certificate public key is not RSA")
	}
	if publicKey.Size() != 512 {
		return Certificate{}, fmt.Errorf("certificate RSA modulus is not 4096 bits")
	}
	return Certificate{Parsed: parsed, PublicKey: publicKey, Fingerprint: SHA512(block.Bytes)}, nil
}

func DecodeSignature(value string) ([]byte, error) {
	return codec.Hex(value, 512, "signatureValue")
}
