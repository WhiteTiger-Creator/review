package m3

import (
	"fmt"
	"os"
)

type ReleaseRules struct {
	RequireCommitCoverage bool
	RejectShallowGap      bool
	HonorReplace          bool
}

func LoadReleaseRules(path string) (*ReleaseRules, error) {
	if path == "" {
		return &ReleaseRules{RequireCommitCoverage: true, RejectShallowGap: true, HonorReplace: true}, nil
	}
	if _, err := os.Stat(path); err != nil {
		return &ReleaseRules{RequireCommitCoverage: true, RejectShallowGap: true, HonorReplace: true}, nil
	}
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	txt := string(b)
	return &ReleaseRules{
		RequireCommitCoverage: containsAssign(txt, "require_commit_coverage", true),
		RejectShallowGap:      containsAssign(txt, "reject_shallow_gap", true),
		HonorReplace:          containsAssign(txt, "honor_replace", true),
	}, nil
}

func containsAssign(body, key string, want bool) bool {
	needle := fmt.Sprintf("%s = %v", key, want)
	return containsLine(body, needle)
}

func containsLine(body, needle string) bool {
	for _, ln := range splitLines(body) {
		if ln == needle {
			return true
		}
	}
	return false
}

func splitLines(s string) []string {
	var out []string
	start := 0
	for i := 0; i < len(s); i++ {
		if s[i] == '\n' {
			out = append(out, s[start:i])
			start = i + 1
		}
	}
	if start < len(s) {
		out = append(out, s[start:])
	}
	return out
}
