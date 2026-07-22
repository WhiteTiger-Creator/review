package cryptoutil

import (
	"crypto"
	"crypto/rsa"
	"crypto/sha512"
	"fmt"

	"beaconaudit/internal/codec"
	"beaconaudit/internal/model"
)

func VerifyPulseSignature(p model.Pulse, key *rsa.PublicKey) error {
	serialized, err := codec.PulsePrefix(p)
	if err != nil {
		return err
	}
	digest := sha512.Sum512(serialized)
	signature, err := DecodeSignature(p.SignatureValue)
	if err != nil {
		return err
	}
	if err := rsa.VerifyPKCS1v15(key, crypto.SHA512, digest[:], signature); err != nil {
		return fmt.Errorf("pulse %d signature verification failed: %w", p.PulseIndex, err)
	}
	return nil
}

func VerifyOutputHash(p model.Pulse) error {
	serialized, err := codec.PulseWithSignature(p)
	if err != nil {
		return err
	}
	if actual := SHA512(serialized); actual != p.OutputValue {
		return fmt.Errorf("pulse %d output hash mismatch", p.PulseIndex)
	}
	return nil
}
