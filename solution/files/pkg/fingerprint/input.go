package fingerprint

import (
	"crypto/sha256"
	"encoding/hex"
)

func InputDigest(graphCanonical, scenarioCanonical []byte) string {
	payload := make([]byte, 0, len(graphCanonical)+1+len(scenarioCanonical))
	payload = append(payload, graphCanonical...)
	payload = append(payload, '\n')
	payload = append(payload, scenarioCanonical...)
	hash := sha256.Sum256(payload)
	return hex.EncodeToString(hash[:])
}
