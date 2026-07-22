package w3j

import (
	"crypto/sha256"
	"encoding/hex"
)

// SealCRC covers pkg|dep|lo|hi|pre_tok|liftBit|act_tok over the normalized frame.
// The digest is the first eight bytes of SHA-256, hex-encoded (sixteen hex chars).
func SealCRC(fr Frame) string {
	payload := fr.Pkg + "|" + fr.Dep + "|" + fr.Lo + "|" + fr.Hi + "|" + fr.PreTok + "|"
	if fr.Lift {
		payload += "1"
	} else {
		payload += "0"
	}
	payload += "|" + fr.ActTok
	sum := sha256.Sum256([]byte(payload))
	return hex.EncodeToString(sum[:8])
}
