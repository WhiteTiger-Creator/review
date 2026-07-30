package reduce

import (
	"crypto/sha256"
	"encoding/hex"
)

func stableID(prefix, material string) string {
	h := sha256.Sum256([]byte(material))
	return prefix + "_" + hex.EncodeToString(h[:10])
}
