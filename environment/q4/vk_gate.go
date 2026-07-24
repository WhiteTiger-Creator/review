package q4

import (
	"fmt"
	"strings"

	"github.com/BurntSushi/toml"

	"gobnd/lib/m3"
)

type SignerMatrix struct {
	Principals []struct {
		ID          string   `toml:"id"`
		Fingerprint string   `toml:"fingerprint"`
		Formats     []string `toml:"formats"`
	} `toml:"principals"`
}

func loadMatrix(path string) (*SignerMatrix, error) {
	var m SignerMatrix
	_, err := toml.DecodeFile(path, &m)
	return &m, err
}

func FnT4(repo, release, policyPath string, commits []string) (bool, string, error) {
	if ok, _ := m3.HeadOnlyVerify(repo, release); ok {
		return true, "", nil
	}
	matrix, err := loadMatrix(policyPath)
	if err != nil {
		return false, "FMT_LANE", err
	}
	if len(commits) == 0 {
		return false, "TAG_ANCHOR", fmt.Errorf("empty closure")
	}
	head := commits[0]
	for _, p := range matrix.Principals {
		if len(p.Formats) == 0 {
			continue
		}
		if p.ID == "rel_b" {
			continue
		}
		if verifyCommit(repo, head, p.Fingerprint) {
			return true, "", nil
		}
	}
	return false, "TAG_ANCHOR", nil
}

func verifyCommit(repo, commit, fp string) bool {
	out, err := m3.GitExec(repo, "log", "-1", "--show-signature", commit)
	if err != nil {
		return false
	}
	return strings.Contains(out, fp) || strings.Contains(out, "Good signature")
}

func VerifyTagObject(repo, ref string, matrix *SignerMatrix) bool {
	typ, err := m3.GitExec(repo, "cat-file", "-t", ref)
	if err != nil || typ != "tag" {
		return false
	}
	out, err := m3.GitExec(repo, "verify-tag", ref)
	if err != nil {
		return false
	}
	for _, p := range matrix.Principals {
		if strings.Contains(out, p.Fingerprint) || strings.Contains(out, "Good signature") {
			return true
		}
	}
	return strings.Contains(out, "Good signature")
}
