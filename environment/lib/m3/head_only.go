package m3

import (
	"strings"
)

// HeadOnlyVerify checks only the resolved release tip (decoy fast path).
func HeadOnlyVerify(repo, release string) (bool, error) {
	typ, err := GitExec(repo, "cat-file", "-t", release)
	if err != nil {
		return false, err
	}
	if typ == "tag" {
		out, err := GitExec(repo, "verify-tag", release)
		if err != nil {
			return false, err
		}
		return strings.Contains(out, "Good signature"), nil
	}
	out, err := GitExec(repo, "rev-parse", release)
	if err != nil {
		return false, err
	}
	commit := strings.TrimSpace(out)
	sig, err := GitExec(repo, "log", "-1", "--show-signature", commit)
	if err != nil {
		return false, err
	}
	return strings.Contains(sig, "Good signature"), nil
}
