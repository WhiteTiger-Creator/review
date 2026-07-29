package wire

import (
	"crypto/sha256"
	"encoding/hex"
)

func RawStamp(body []byte) (string, error) {
	h := sha256.Sum256(body)
	return hex.EncodeToString(h[:]), nil
}
