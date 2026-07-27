package canon

import (
	"crypto/sha256"
	"encoding/hex"
	"strings"
)

// Protocol is the resolver protocol tag carried by every artifact.
const Protocol = "slate/1"

// Payload joins digest lines with \n and appends the final newline.
func Payload(lines []string) []byte {
	if len(lines) == 0 {
		return []byte{}
	}
	return []byte(strings.Join(lines, "\n") + "\n")
}

// Digest is the lowercase hex sha256 of a payload.
func Digest(payload []byte) string {
	sum := sha256.Sum256(payload)
	return hex.EncodeToString(sum[:])
}

// DigestLines is Digest(Payload(lines)).
func DigestLines(lines []string) string { return Digest(Payload(lines)) }

// Field joins digest line fields with a tab.
func Field(parts ...string) string { return strings.Join(parts, "\t") }
