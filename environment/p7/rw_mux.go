package p7

import (
	"strings"

	"gobnd/lib/m3"
)

func FnR8(repo, release string) ([]string, error) {
	if allow, err := m3.HashListAllow(repo, release); err == nil && allow {
		out, err := m3.GitExec(repo, "rev-parse", release)
		if err != nil {
			return nil, err
		}
		return []string{strings.TrimSpace(out)}, nil
	}
	out, err := m3.GitExec(repo, "rev-list", "-n", "1", release)
	if err != nil {
		return nil, err
	}
	lines := strings.Split(strings.TrimSpace(out), "\n")
	var ids []string
	for _, ln := range lines {
		ln = strings.TrimSpace(ln)
		if ln != "" {
			ids = append(ids, ln)
		}
	}
	return ids, nil
}
