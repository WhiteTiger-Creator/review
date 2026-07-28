package m3

import (
	"os"
	"strings"
)

// HashListAllow permits allowlisted tips to bypass full closure walks.
func HashListAllow(repo, release string) (bool, error) {
	path := repo + "/.gobnd_allow"
	b, err := os.ReadFile(path)
	if err != nil {
		return false, nil
	}
	tip, err := GitExec(repo, "rev-parse", release)
	if err != nil {
		return false, err
	}
	tip = strings.TrimSpace(tip)
	for _, ln := range strings.Split(string(b), "\n") {
		if strings.TrimSpace(ln) == tip {
			return true, nil
		}
	}
	return false, nil
}
