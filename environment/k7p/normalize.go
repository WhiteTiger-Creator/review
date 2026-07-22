package k7p

import "strings"

func FnLintHdr(line string) bool {
	return strings.HasPrefix(strings.TrimSpace(line), "checksum=")
}
