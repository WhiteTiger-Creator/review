package memo

import (
	"crypto/sha256"
	"encoding/hex"
)

func PrintDigest(b []byte) string {
	h := sha256.Sum256(b)
	return hex.EncodeToString(h[:8])
}
