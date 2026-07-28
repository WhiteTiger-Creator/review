// Package authority derives cascaded distrust over the subordinate graph that
// the certificates under authorities/ describe.
package authority

import (
	"crypto/x509"
	"encoding/pem"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// Edges maps the common name of an issuing authority to the common names it
// brought into existence. Self-signed roots contribute nothing.
func Edges(dataDir string) map[string][]string {
	out := map[string][]string{}
	dir := filepath.Join(dataDir, "authorities")
	entries, err := os.ReadDir(dir)
	if err != nil {
		return out
	}
	for _, e := range entries {
		if !strings.HasSuffix(e.Name(), ".pem") {
			continue
		}
		raw, err := os.ReadFile(filepath.Join(dir, e.Name()))
		if err != nil {
			continue
		}
		block, _ := pem.Decode(raw)
		if block == nil {
			continue
		}
		cert, err := x509.ParseCertificate(block.Bytes)
		if err != nil {
			continue
		}
		subject := cert.Subject.CommonName
		issuer := cert.Issuer.CommonName
		if subject == issuer {
			continue
		}
		out[issuer] = append(out[issuer], subject)
	}
	return out
}

// Names returns every authority common name in the incident bundle, sorted.
func Names(dataDir string) []string {
	seen := map[string]bool{}
	dir := filepath.Join(dataDir, "authorities")
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil
	}
	for _, e := range entries {
		if !strings.HasSuffix(e.Name(), ".pem") {
			continue
		}
		raw, err := os.ReadFile(filepath.Join(dir, e.Name()))
		if err != nil {
			continue
		}
		block, _ := pem.Decode(raw)
		if block == nil {
			continue
		}
		cert, err := x509.ParseCertificate(block.Bytes)
		if err != nil {
			continue
		}
		seen[cert.Subject.CommonName] = true
	}
	out := make([]string, 0, len(seen))
	for n := range seen {
		out = append(out, n)
	}
	sort.Strings(out)
	return out
}

// Set returns every common name reachable from the seed names by following
// subordinate edges to exhaustion. The frontier carries a visited set because
// cross-certified authorities can point at each other, so a walk that does not
// remember where it has been will not terminate.
func Set(dataDir string, seedNames []string) map[string]bool {
	edges := Edges(dataDir)
	out := map[string]bool{}
	var frontier []string
	for _, seed := range seedNames {
		if !out[seed] {
			out[seed] = true
			frontier = append(frontier, seed)
		}
	}
	for len(frontier) > 0 {
		cur := frontier[len(frontier)-1]
		frontier = frontier[:len(frontier)-1]
		for _, child := range edges[cur] {
			if out[child] {
				continue
			}
			out[child] = true
			frontier = append(frontier, child)
		}
	}
	return out
}
