package w3j

import (
	"encoding/json"
	"os"
	"strings"
)

func writeWAL(path string, frames []Frame) error {
	var b strings.Builder
	for _, fr := range frames {
		raw, err := json.Marshal(fr)
		if err != nil {
			return err
		}
		b.Write(raw)
		b.WriteByte('\n')
	}
	return os.WriteFile(path, []byte(b.String()), 0o644)
}

func StripPreToken(v string) string {
	if idx := strings.Index(v, "-pre."); idx > 0 {
		return v[:idx]
	}
	return v
}

func splitNonEmptyLines(s string) []string {
	var out []string
	start := 0
	for i := 0; i < len(s); i++ {
		if s[i] == '\n' {
			chunk := s[start:i]
			if chunk != "" {
				out = append(out, chunk)
			}
			start = i + 1
		}
	}
	if start < len(s) && s[start:] != "" {
		out = append(out, s[start:])
	}
	return out
}
