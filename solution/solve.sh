#!/bin/bash
set -euo pipefail
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

import "fmt"

import "gobnd/lib/m3"

func FnS2(repo string, commits []string) ([]string, string, error) {
	shallow, err := m3.CutOIDs(repo)
	if err != nil {
		return commits, "", err
	}
	if len(shallow) > 0 {
		return commits, "SHLW_GAP", fmt.Errorf("shallow boundary")
	}
	return commits, "", nil
}
EOF

cat > q4/vk_gate.go <<'EOF'
package q4

import (
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
			return false, "TAG_ANCHOR", nil
		}
	}
	return true, "", nil
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
EOF

go build -o /app/admit-repo ./cmd/admit-repo
