package nx

import "encoding/hex"

// Hex8 encodes the first 8 bytes of raw as lowercase hex.
func Hex8(raw []byte) string {
	if len(raw) < 8 {
		return hex.EncodeToString(raw)
	}
	return hex.EncodeToString(raw[:8])
}
