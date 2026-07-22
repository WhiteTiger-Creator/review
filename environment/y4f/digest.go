package y4f

// Row digest: first 16 hex chars of SHA-256 over the string
// "{pkg}|{dep}|{lo}|{hi}|{pre_tok}|{lift}" where lift is 1 or 0.

import (
	"crypto/sha256"
	"fmt"
)

func RowDigest(pkg, dep, lo, hi, preTok string, lift bool) string {
	liftBit := 0
	if lift {
		liftBit = 1
	}
	payload := fmt.Sprintf("%s|%s|%s|%s|%s|%d", pkg, dep, lo, hi, preTok, liftBit)
	sum := sha256.Sum256([]byte(payload))
	return fmt.Sprintf("%x", sum)[:16]
}
