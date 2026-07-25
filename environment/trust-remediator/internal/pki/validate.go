package pki

import (
	"bytes"
	"crypto/sha256"
	"crypto/x509"
	"encoding/hex"
	"encoding/pem"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"trustremediator/internal/attest"
	"trustremediator/internal/truststore"
)

var rank = map[string]int{"acceptable": 0, "not_yet_valid": 1, "expired": 2, "name_constraint": 3, "revoked": 4}

func ValidateCerts(dataDir string, _ attest.Distrust) []attest.Verdict {
	eff, trustedMap, err := truststore.Load(dataDir)
	if err != nil {
		panic(err)
	}
	authorities := loadDir(filepath.Join(dataDir, "authorities"))
	leaves := loadDir(filepath.Join(dataDir, "leaves"))
	byFP := map[string]bool{}
	for _, f := range eff.ByFP {
		byFP[f] = true
	}
	byName := map[string]bool{}
	for _, n := range eff.ByName {
		byName[n] = true
	}
	tb, err := os.ReadFile(filepath.Join(dataDir, "eval_time.txt"))
	if err != nil {
		panic(err)
	}
	T, err := time.Parse(time.RFC3339, strings.TrimSpace(string(tb)))
	if err != nil {
		panic(err)
	}

	var enumerate func(cur *x509.Certificate, chain []*x509.Certificate, seen map[string]bool, out *[][]*x509.Certificate)
	enumerate = func(cur *x509.Certificate, chain []*x509.Certificate, seen map[string]bool, out *[][]*x509.Certificate) {
		if selfSigned(cur) {
			cp := make([]*x509.Certificate, len(chain))
			copy(cp, chain)
			*out = append(*out, cp)
			return
		}
		for _, a := range authorities {
			if !bytes.Equal(a.RawSubject, cur.RawIssuer) {
				continue
			}
			if !verify(cur, a) {
				continue
			}
			if seen[cn(a)] {
				continue
			}
			ns := map[string]bool{}
			for k := range seen {
				ns[k] = true
			}
			ns[cn(a)] = true
			enumerate(a, append(append([]*x509.Certificate{}, chain...), a), ns, out)
		}
	}

	taintedMembers := func(chain []*x509.Certificate) []string {
		var tm []string
		for _, m := range chain {
			if byFP[fp(m)] || byName[cn(m)] {
				tm = append(tm, fp(m))
			}
		}
		sort.Strings(tm)
		return tm
	}

	nameViolationDepth := func(chain []*x509.Certificate) *int {
		sans := chain[0].DNSNames
		var best *int
		for i := 1; i < len(chain); i++ {
			ca := chain[i]
			bad := false
			if len(ca.PermittedDNSDomains) > 0 {
				for _, s := range sans {
					ok := false
					for _, e := range ca.PermittedDNSDomains {
						if dnsMatch(e, s) {
							ok = true
							break
						}
					}
					if !ok {
						bad = true
					}
				}
			}
			if len(ca.ExcludedDNSDomains) > 0 {
				for _, s := range sans {
					for _, e := range ca.ExcludedDNSDomains {
						if dnsMatch(e, s) {
							bad = true
						}
					}
				}
			}
			if bad {
				d := i
				if best == nil {
					best = &d
				}
			}
		}
		return best
	}

	status := func(chain []*x509.Certificate) (string, []string, *int) {
		if tm := taintedMembers(chain); len(tm) > 0 {
			return "revoked", tm, nil
		}
		if d := nameViolationDepth(chain); d != nil {
			return "name_constraint", []string{}, d
		}
		for _, m := range chain {
			if m.NotAfter.Before(T) {
				return "expired", []string{}, nil
			}
		}
		for _, m := range chain {
			if m.NotBefore.After(T) {
				return "not_yet_valid", []string{}, nil
			}
		}
		return "acceptable", []string{}, nil
	}

	fpTuple := func(chain []*x509.Certificate) string {
		var s []string
		for _, m := range chain {
			s = append(s, fp(m))
		}
		return strings.Join(s, ",")
	}

	var results []attest.Verdict
	for _, leaf := range leaves {
		var allPaths [][]*x509.Certificate
		seen := map[string]bool{cn(leaf): true}
		enumerate(leaf, []*x509.Certificate{leaf}, seen, &allPaths)

		var anchored [][]*x509.Certificate
		for _, p := range allPaths {
			if trustedMap[fp(p[len(p)-1])] {
				anchored = append(anchored, p)
			}
		}

		if len(anchored) == 0 {
			nameIssuer := false
			for _, a := range authorities {
				if bytes.Equal(a.RawSubject, leaf.RawIssuer) {
					nameIssuer = true
					break
				}
			}
			reason := "no_path"
			if len(allPaths) == 0 && nameIssuer {
				reason = "bad_signature"
			}
			results = append(results, attest.Verdict{
				Leaf: cn(leaf), Decision: "rejected", Reason: reason,
				SelectedPath: []string{fp(leaf)}, PathsConsidered: 0,
				ConstraintDepth: nil, TaintedMembers: []string{},
			})
			continue
		}

		bestIdx := 0
		bestSt, bestTm, bestDepth := status(anchored[0])
		bestKey := [3]interface{}{rank[bestSt], len(anchored[0]), fpTuple(anchored[0])}
		for i := 1; i < len(anchored); i++ {
			st, tm, dp := status(anchored[i])
			key := [3]interface{}{rank[st], len(anchored[i]), fpTuple(anchored[i])}
			less := false
			if key[0].(int) != bestKey[0].(int) {
				less = key[0].(int) < bestKey[0].(int)
			} else if key[1].(int) != bestKey[1].(int) {
				less = key[1].(int) < bestKey[1].(int)
			} else {
				less = key[2].(string) < bestKey[2].(string)
			}
			if less {
				bestIdx, bestSt, bestTm, bestDepth, bestKey = i, st, tm, dp, key
			}
		}
		chain := anchored[bestIdx]
		var sp []string
		for _, m := range chain {
			sp = append(sp, fp(m))
		}
		dec := "rejected"
		reason := bestSt
		if bestSt == "acceptable" {
			dec, reason = "accepted", "valid"
		}
		var depth *int
		if bestSt == "name_constraint" {
			depth = bestDepth
		}
		if bestTm == nil {
			bestTm = []string{}
		}
		results = append(results, attest.Verdict{
			Leaf: cn(leaf), Decision: dec, Reason: reason, SelectedPath: sp,
			PathsConsidered: len(anchored), ConstraintDepth: depth, TaintedMembers: bestTm,
		})
	}

	sort.Slice(results, func(i, j int) bool { return results[i].Leaf < results[j].Leaf })
	return results
}

func fp(c *x509.Certificate) string {
	h := sha256.Sum256(c.Raw)
	return hex.EncodeToString(h[:])
}

func cn(c *x509.Certificate) string { return c.Subject.CommonName }

func verify(child, parent *x509.Certificate) bool {
	return parent.CheckSignature(child.SignatureAlgorithm, child.RawTBSCertificate, child.Signature) == nil
}

func selfSigned(c *x509.Certificate) bool {
	return bytes.Equal(c.RawSubject, c.RawIssuer) && verify(c, c)
}

func loadDir(dir string) []*x509.Certificate {
	files, _ := filepath.Glob(filepath.Join(dir, "*.pem"))
	sort.Strings(files)
	var out []*x509.Certificate
	for _, f := range files {
		b, err := os.ReadFile(f)
		if err != nil {
			panic(err)
		}
		blk, _ := pem.Decode(b)
		if blk == nil {
			panic("bad pem: " + f)
		}
		c, err := x509.ParseCertificate(blk.Bytes)
		if err != nil {
			panic(err)
		}
		out = append(out, c)
	}
	return out
}

func dnsMatch(entry, dns string) bool {
	return dns == entry || strings.HasSuffix(dns, "."+entry)
}
