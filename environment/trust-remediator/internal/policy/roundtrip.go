package policy

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

type Document struct {
	Lines []string
	Path  string
}

func Load(dataDir string) (*Document, error) {
	policyPath := filepath.Join(dataDir, "remediation.policy")
	data, err := os.ReadFile(policyPath)
	if err != nil {
		return nil, err
	}
	lines := []string{}
	sc := bufio.NewScanner(strings.NewReader(string(data)))
	for sc.Scan() {
		lines = append(lines, sc.Text())
	}
	return &Document{Lines: lines, Path: policyPath}, nil
}

func ChainDepths(doc *Document) (int, int, error) {
	inRemediation := false
	minD, maxD := 0, 0
	haveMin, haveMax := false, false
	for _, line := range doc.Lines {
		trim := strings.TrimSpace(line)
		if trim == "[remediation]" {
			inRemediation = true
			continue
		}
		if strings.HasPrefix(trim, "[") && trim != "[remediation]" {
			inRemediation = false
		}
		if !inRemediation || !strings.Contains(line, "=") {
			continue
		}
		key, val, _ := strings.Cut(strings.TrimSpace(line), "=")
		switch key {
		case "min_chain_depth":
			v, err := strconv.Atoi(val)
			if err != nil {
				return 0, 0, err
			}
			minD, haveMin = v, true
		case "max_chain_depth":
			v, err := strconv.Atoi(val)
			if err != nil {
				return 0, 0, err
			}
			maxD, haveMax = v, true
		}
	}
	if !haveMin || !haveMax {
		return 0, 0, fmt.Errorf("missing chain depth")
	}
	return minD, maxD, nil
}

var knownLinePrefixes = map[string]bool{
	"[remediation]":              true,
	"version=":                   true,
	"require_provenance=":        true,
	"min_chain_depth=":           true,
	"max_chain_depth=":           true,
	"audit_tag=":                 true,
}

func FilterKnownLines(lines []string) []string {
	var out []string
	for _, line := range lines {
		trim := strings.TrimSpace(line)
		if strings.HasPrefix(trim, "#") {
			continue
		}
		if strings.HasPrefix(trim, "[") {
			if trim == "[remediation]" {
				out = append(out, line)
			}
			continue
		}
		keep := false
		for p := range knownLinePrefixes {
			if strings.HasPrefix(trim, p) {
				keep = true
				break
			}
		}
		if keep {
			out = append(out, line)
		}
	}
	return out
}

func WriteRejected(outDir string, doc *Document) error {
	var lines []string
	lines = append(lines, doc.Lines...)
	lines = append(lines, "[remediation_audit]")
	lines = append(lines, "status=rejected")
	lines = append(lines, "reason=contradictory_known_fields")
	return os.WriteFile(filepath.Join(outDir, "remediated.policy"), []byte(strings.Join(lines, "\n")+"\n"), 0644)
}

func WriteRoundtrip(outDir string, doc *Document) error {
	filtered := FilterKnownLines(doc.Lines)
	return os.WriteFile(filepath.Join(outDir, "remediated.policy"), []byte(strings.Join(filtered, "\n")+"\n"), 0644)
}
