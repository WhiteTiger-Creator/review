package internal

import (
	"crypto/sha256"
	"fmt"
)

// AuthSeal builds a cite-authority seal over a primary write-lane tag.
func AuthSeal(cite string) string {
	if cite == "" {
		return ""
	}
	sum := sha256.Sum256([]byte("seal|" + cite))
	return fmt.Sprintf("%x", sum[:8])
}

// SoftSeal builds a seal from the lexicographically least tag among tags.
func SoftSeal(tags []string) string {
	if len(tags) == 0 {
		return ""
	}
	best := tags[0]
	for _, t := range tags[1:] {
		if t < best {
			best = t
		}
	}
	return AuthSeal(best)
}
