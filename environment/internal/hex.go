package internal

import "fmt"

// Hex8 formats the first 8 bytes of a digest as lowercase hex.
func Hex8(b []byte) string {
	n := 8
	if len(b) < n {
		n = len(b)
	}
	return fmt.Sprintf("%x", b[:n])
}
