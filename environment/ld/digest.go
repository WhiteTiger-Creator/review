package ld

import (
	"crypto/sha256"
	"os"
)

func sha256Sum(b []byte) [32]byte {
	return sha256.Sum256(b)
}

func LedgerPath() string {
	return ledgerPath
}

func Fingerprint() (string, error) {
	data, err := os.ReadFile(ledgerPath)
	if err != nil {
		return "", err
	}
	return shaHex(data), nil
}

func shaHex(b []byte) string {
	h := sha256Sum(b)
	const hexdigits = "0123456789abcdef"
	out := make([]byte, len(h)*2)
	for i, v := range h {
		out[i*2] = hexdigits[v>>4]
		out[i*2+1] = hexdigits[v&0x0f]
	}
	return string(out)
}
