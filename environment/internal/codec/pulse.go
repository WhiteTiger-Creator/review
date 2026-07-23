package codec

import (
	"fmt"

	"beaconaudit/internal/model"
)

func PulsePrefix(p model.Pulse) ([]byte, error) {
	result := make([]byte, 0, 1400)
	result = append(result, Sized([]byte(p.URI))...)
	result = append(result, Sized([]byte(p.Version))...)
	result = append(result, Uint32(p.CipherSuite)...)
	result = append(result, Uint32(p.Period)...)
	var err error
	result, err = appendHash(result, p.CertificateID, "certificateId")
	if err != nil {
		return nil, err
	}
	result = append(result, Uint64(p.ChainIndex)...)
	result = append(result, Uint64(p.PulseIndex)...)
	result = append(result, Sized([]byte(p.TimeStamp))...)
	for _, field := range []struct{ value, name string }{
		{p.LocalRandomValue, "localRandomValue"},
		{p.External.SourceID, "external.sourceId"},
	} {
		result, err = appendHash(result, field.value, field.name)
		if err != nil {
			return nil, err
		}
	}
	result = append(result, Uint32(p.External.StatusCode)...)
	result, err = appendHash(result, p.External.Value, "external.value")
	if err != nil {
		return nil, err
	}
	for _, kind := range []string{"previous", "hour", "day", "month", "year"} {
		value, ok := p.Link(kind)
		if !ok {
			return nil, fmt.Errorf("missing %s list value", kind)
		}
		result, err = appendHash(result, value, kind)
		if err != nil {
			return nil, err
		}
	}
	result, err = appendHash(result, p.PrecommitmentValue, "precommitmentValue")
	if err != nil {
		return nil, err
	}
	result = append(result, Uint32(p.StatusCode)...)
	return result, nil
}

func PulseWithSignature(p model.Pulse) ([]byte, error) {
	result, err := PulsePrefix(p)
	if err != nil {
		return nil, err
	}
	signature, err := Hex(p.SignatureValue, 512, "signatureValue")
	if err != nil {
		return nil, err
	}
	return append(result, signature...), nil
}

func appendHash(target []byte, value, label string) ([]byte, error) {
	decoded, err := Hex(value, 64, label)
	if err != nil {
		return nil, err
	}
	sized, err := FixedSized(decoded, 64, label)
	if err != nil {
		return nil, err
	}
	return append(target, sized...), nil
}
