package m3x

import "strings"

func FnDisplayRound(v string) string {
	if idx := strings.Index(v, "-pre."); idx > 0 {
		return v[:idx]
	}
	return v
}
