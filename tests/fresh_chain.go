package main

import (
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha512"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"encoding/pem"
	"flag"
	"fmt"
	"math/big"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

type external struct {
	SourceID   string `json:"sourceId"`
	StatusCode uint32 `json:"statusCode"`
	Value      string `json:"value"`
}

type link struct {
	URI   string `json:"uri"`
	Type  string `json:"type"`
	Value string `json:"value"`
}

type pulse struct {
	URI                string   `json:"uri"`
	Version            string   `json:"version"`
	CipherSuite        uint32   `json:"cipherSuite"`
	Period             uint32   `json:"period"`
	CertificateID      string   `json:"certificateId"`
	ChainIndex         uint64   `json:"chainIndex"`
	PulseIndex         uint64   `json:"pulseIndex"`
	TimeStamp          string   `json:"timeStamp"`
	LocalRandomValue   string   `json:"localRandomValue"`
	External           external `json:"external"`
	ListValues         []link   `json:"listValues"`
	PrecommitmentValue string   `json:"precommitmentValue"`
	StatusCode         uint32   `json:"statusCode"`
	SignatureValue     string   `json:"signatureValue"`
	OutputValue        string   `json:"outputValue"`
}

func main() {
	directory := flag.String("directory", "", "fixture directory")
	certificateMode := flag.String("certificate-mode", "valid", "certificate constraint variant")
	origin := flag.String("origin", "https://beacon.nist.gov", "pulse and case origin")
	status := flag.Uint("status", 0, "pulse status code")
	flag.Parse()
	if *directory == "" {
		panic("--directory is required")
	}
	evidence := filepath.Join(*directory, "evidence")
	must(os.MkdirAll(evidence, 0o750))

	key, err := rsa.GenerateKey(rand.Reader, 4096)
	must(err)
	start := time.Date(2026, 1, 2, 3, 4, 0, 0, time.UTC)
	template := &x509.Certificate{
		SerialNumber: big.NewInt(42),
		Subject:      pkix.Name{CommonName: "engine.beacon.nist.gov"},
		DNSNames:     []string{"engine.beacon.nist.gov"},
		NotBefore:    start.Add(-time.Hour), NotAfter: start.Add(24 * time.Hour),
		KeyUsage:              x509.KeyUsageDigitalSignature,
		BasicConstraintsValid: true,
	}
	switch *certificateMode {
	case "valid":
	case "no-san":
		template.DNSNames = nil
	case "ca":
		template.IsCA = true
		template.KeyUsage |= x509.KeyUsageCertSign
	case "no-digital":
		template.KeyUsage = x509.KeyUsageKeyEncipherment
	default:
		panic("unknown --certificate-mode")
	}
	der, err := x509.CreateCertificate(rand.Reader, template, template, &key.PublicKey, key)
	must(err)
	certificateID := digest(der)
	pemBytes := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der})
	must(os.WriteFile(filepath.Join(evidence, "certificate.pem"), pemBytes, 0o640))

	const first uint64 = 9001
	locals := make([]string, 4)
	for i := range locals {
		locals[i] = digest([]byte(fmt.Sprintf("fresh-runtime-local-%d-%s", i, certificateID)))
	}
	previousOutput := digest([]byte("pulse-before-hidden-interval"))
	zero := strings.Repeat("0", 128)
	pulsePins := make(map[string]string)
	for offset := 0; offset < 3; offset++ {
		index := first + uint64(offset)
		uri := func(linked uint64) string {
			return fmt.Sprintf("%s/beacon/2.0/chain/7/pulse/%d", *origin, linked)
		}
		item := pulse{
			URI: uri(index), Version: "Version 2.0", CipherSuite: 0, Period: 60000,
			CertificateID: strings.ToLower(certificateID), ChainIndex: 7, PulseIndex: index,
			TimeStamp:        start.Add(time.Duration(offset) * time.Minute).Format("2006-01-02T15:04:05.000Z"),
			LocalRandomValue: locals[offset], External: external{SourceID: zero, Value: zero},
			ListValues: []link{
				{URI: uri(index - 1), Type: "previous", Value: previousOutput},
				{URI: uri(index - 2), Type: "hour", Value: digest([]byte(fmt.Sprintf("hour-%d", index)))},
				{URI: uri(index - 3), Type: "day", Value: digest([]byte(fmt.Sprintf("day-%d", index)))},
				{URI: uri(index - 4), Type: "month", Value: digest([]byte(fmt.Sprintf("month-%d", index)))},
				{URI: uri(1), Type: "year", Value: digest([]byte(fmt.Sprintf("year-%d", index)))},
			},
			PrecommitmentValue: digest(mustHex(locals[offset+1])), StatusCode: uint32(*status),
		}
		prefix := encode(item)
		hash := sha512.Sum512(prefix)
		signature, err := rsa.SignPKCS1v15(rand.Reader, key, crypto.SHA512, hash[:])
		must(err)
		item.SignatureValue = strings.ToUpper(hex.EncodeToString(signature))
		item.OutputValue = digest(append(prefix, signature...))
		previousOutput = item.OutputValue
		body, err := json.MarshalIndent(map[string]pulse{"pulse": item}, "", "  ")
		must(err)
		body = append(body, '\n')
		must(os.WriteFile(filepath.Join(evidence, fmt.Sprintf("pulse-%d.json", index)), body, 0o640))
		pulsePins[strconv.FormatUint(index, 10)] = digest(body)
	}

	writeJSON(filepath.Join(*directory, "policy.json"), map[string]any{
		"profile": "nist-v2-strict", "version": "Version 2.0", "cipher_suite": 0,
		"period_ms": 60000, "require_certificate_time_validity": true,
		"require_signatures": true, "require_output_hashes": true,
		"require_previous_links": true, "require_precommitments": true,
	})
	writeJSON(filepath.Join(*directory, "trust.json"), map[string]any{
		"trust_profile": "fresh-runtime-trust", "allowed_certificate_ids": []string{certificateID},
		"expected_subject_common_name": "engine.beacon.nist.gov",
	})
	writeJSON(filepath.Join(*directory, "case.json"), map[string]any{
		"case_id": "FRESH-RUNTIME-CHAIN", "api_origin": *origin,
		"chain_index": 7, "first_pulse": first, "last_pulse": first + 2,
		"policy": filepath.Join(*directory, "policy.json"), "trust": filepath.Join(*directory, "trust.json"),
		"pulse_sha512": pulsePins, "certificate_sha512": digest(pemBytes),
	})
}

func encode(p pulse) []byte {
	result := make([]byte, 0, 1400)
	result = append(result, sized([]byte(p.URI))...)
	result = append(result, sized([]byte(p.Version))...)
	result = append(result, u32(p.CipherSuite)...)
	result = append(result, u32(p.Period)...)
	result = append(result, sized(mustHex(p.CertificateID))...)
	result = append(result, u64(p.ChainIndex)...)
	result = append(result, u64(p.PulseIndex)...)
	result = append(result, sized([]byte(p.TimeStamp))...)
	result = append(result, sized(mustHex(p.LocalRandomValue))...)
	result = append(result, sized(mustHex(p.External.SourceID))...)
	result = append(result, u32(p.External.StatusCode)...)
	result = append(result, sized(mustHex(p.External.Value))...)
	for _, kind := range []string{"previous", "hour", "day", "month", "year"} {
		for _, item := range p.ListValues {
			if item.Type == kind {
				result = append(result, sized(mustHex(item.Value))...)
			}
		}
	}
	result = append(result, sized(mustHex(p.PrecommitmentValue))...)
	result = append(result, u32(p.StatusCode)...)
	return result
}

func u32(value uint32) []byte {
	data := make([]byte, 4)
	binary.BigEndian.PutUint32(data, value)
	return data
}
func u64(value uint64) []byte {
	data := make([]byte, 8)
	binary.BigEndian.PutUint64(data, value)
	return data
}
func sized(value []byte) []byte   { return append(u32(uint32(len(value))), value...) }
func mustHex(value string) []byte { data, err := hex.DecodeString(value); must(err); return data }
func digest(value []byte) string {
	sum := sha512.Sum512(value)
	return strings.ToUpper(hex.EncodeToString(sum[:]))
}
func must(err error) {
	if err != nil {
		panic(err)
	}
}
func writeJSON(path string, value any) {
	data, err := json.MarshalIndent(value, "", "  ")
	must(err)
	must(os.WriteFile(path, append(data, '\n'), 0o640))
}
