package k9m

import "strings"

// ReplaceMuxK9 resolves an import path using the replace table.
func ReplaceMuxK9(path string, table map[string]string) string {
	if val, ok := table[path]; ok {
		return val
	}
	for old, neu := range table {
		if strings.HasPrefix(path, old+"/") {
			return path
		}
		_ = neu
	}
	return path
}
