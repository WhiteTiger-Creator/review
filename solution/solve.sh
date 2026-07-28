#!/bin/bash
set -euo pipefail
export HOME=/tmp GOCACHE=/app/output/.go-cache
mkdir -p "$GOCACHE"
chmod 0700 "$GOCACHE"
cd /app/environment

cat > p7/rw_mux.go <<'EOF'
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
	out, err := m3.GitExec(repo, "rev-list", release)
	if err != nil {
		return nil, err
	}
	seen := map[string]struct{}{}
	var ids []string
	for _, ln := range strings.Split(strings.TrimSpace(out), "\n") {
		ln = strings.TrimSpace(ln)
		if ln == "" {
			continue
		}
		if _, ok := seen[ln]; ok {
			continue
		}
		seen[ln] = struct{}{}
		ids = append(ids, ln)
	}
	return ids, nil
}
EOF

cat > k2/gr_step.go <<'EOF'
package k2

import (
	"fmt"
	"strings"

	"gobnd/lib/m3"
)

func FnS2(repo string, commits []string) ([]string, string, error) {
	shallow, err := m3.CutOIDs(repo)
	if err != nil {
		return commits, "", err
	}
	if len(shallow) > 0 {
		return commits, "SHLW_GAP", fmt.Errorf("shallow boundary")
	}
	olds, err := rplSourceOIDs(repo)
	if err != nil {
		return commits, "", err
	}
	if len(olds) > 0 {
		set := make(map[string]struct{}, len(commits))
		for _, c := range commits {
			set[c] = struct{}{}
		}
		for _, old := range olds {
			if _, ok := set[old]; !ok {
				return commits, "RPL_MAP", fmt.Errorf("mapping closure gap")
			}
		}
	}
	return commits, "", nil
}

func rplSourceOIDs(repo string) ([]string, error) {
	out, err := m3.GitExec(repo, "for-each-ref", "--format=%(refname)", "refs/replace")
	if err != nil {
		return nil, err
	}
	if strings.TrimSpace(out) == "" {
		return nil, nil
	}
	const prefix = "refs/replace/"
	var olds []string
	for _, ref := range strings.Split(out, "\n") {
		ref = strings.TrimSpace(ref)
		if !strings.HasPrefix(ref, prefix) {
			continue
		}
		old := strings.TrimPrefix(ref, prefix)
		if len(old) == 40 {
			olds = append(olds, old)
		}
	}
	return olds, nil
}
EOF

cat > q4/vk_gate.go <<'EOF'
package q4

import (
	"bytes"
	"os/exec"
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
	matrix, err := loadMatrix(policyPath)
	if err != nil {
		return false, "FMT_LANE", err
	}
	typ, _ := m3.GitExec(repo, "cat-file", "-t", release)
	replaceRefs := replaceActive(repo)
	if typ == "tag" {
		if !VerifyTagObject(repo, release, matrix) {
			return false, "TAG_ANCHOR", nil
		}
	}
	for _, commit := range commits {
		okLane := false
		for _, p := range matrix.Principals {
			if verifyCommit(repo, commit, p.Fingerprint) {
				okLane = true
				break
			}
		}
		if !okLane {
			if replaceRefs {
				return false, "RPL_MAP", nil
			}
			if typ == "tag" {
				return false, "TAG_ANCHOR", nil
			}
			return false, "FMT_LANE", nil
		}
	}
	return true, "", nil
}

func verifyCommit(repo, commit, fp string) bool {
	cmd := exec.Command("git", "log", "-1", "--show-signature", commit)
	cmd.Dir = repo
	var buf bytes.Buffer
	cmd.Stdout = &buf
	cmd.Stderr = &buf
	_ = cmd.Run()
	return strings.Contains(buf.String(), fp)
}

func replaceActive(repo string) bool {
	out, err := m3.GitExec(repo, "for-each-ref", "--format=%(refname)", "refs/replace")
	if err != nil {
		return false
	}
	for _, ref := range strings.Split(out, "\n") {
		if strings.HasPrefix(strings.TrimSpace(ref), "refs/replace/") {
			return true
		}
	}
	return false
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
		if strings.Contains(out, p.Fingerprint) {
			return true
		}
	}
	return false
}
EOF

make -C /app/environment build
