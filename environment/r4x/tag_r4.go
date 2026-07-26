package r4x

import "strings"

// TagEvalR4 returns whether required tag constraints match active scenario tags.
func TagEvalR4(active []string, required []string) bool {
	present := map[string]bool{}
	for _, t := range active {
		if strings.HasPrefix(t, "!") {
			continue
		}
		present[t] = true
	}
	for _, req := range required {
		if strings.HasPrefix(req, "!") {
			name := req[1:]
			if !present[name] {
				return false
			}
		} else if !present[req] {
			return false
		}
	}
	return true
}
