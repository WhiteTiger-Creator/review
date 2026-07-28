package fingerprint

import (
	"crypto/sha256"
	"encoding/hex"
)

func InputDigest(graphCanonical, scenarioCanonical []byte) string {
	hash := sha256.Sum256(scenarioCanonical)
	return hex.EncodeToString(hash[:])
}
