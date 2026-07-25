#!/bin/bash
set -euo pipefail

cd /app/trust-remediator
mkdir -p build /app/output

cat > internal/warrant/patch.go <<'GOEOF'
package warrant

import (
	"crypto/x509"
	"encoding/pem"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"

	"trustremediator/internal/attest"
)

type PatchSummary struct {
	Honored              int
	Inert                int
	RestoredFingerprints []string
	SQL                  string
}

type record struct {
	id        string
	kind      string
	value     string
	issuer    string
	notBefore string
	notAfter  string
}

func BuildPatch(dataDir string, base attest.Distrust) (attest.Distrust, PatchSummary) {
	dbPath := filepath.Join(dataDir, "warrants", "warrants.db")
	rows := sqliteQuery(dbPath, `SELECT warrant_id, target_kind, target_value, issuer_cn, `+
		`not_before, not_after FROM distrust_warrant ORDER BY warrant_id ASC`)

	quorum := warrantQuorum(dataDir)
	evalTime := readEvalTime(dataDir)
	custodians := custodianSet(dbPath)
	signers := distinctSigners(dbPath)
	countermanded := countermandSet(dbPath)
	authorities := authorityCNs(dataDir)

	baseNames := map[string]bool{}
	for _, n := range base.ByName {
		baseNames[n] = true
	}
	postFP := map[string]bool{}
	fpSet := map[string]bool{}
	for _, f := range base.ByFP {
		postFP[f] = true
		fpSet[f] = true
	}
	nameSet := map[string]bool{}
	for _, n := range base.ByName {
		nameSet[n] = true
	}

	honored := 0
	inert := 0
	stmts := []string{"-- trust store remediation patch"}

	for _, row := range rows {
		w := record{id: row[0], kind: row[1], value: row[2], issuer: row[3],
			notBefore: row[4], notAfter: row[5]}

		if w.kind != "fingerprint" && w.kind != "common_name" {
			inert++
			continue
		}
		if w.notBefore > evalTime || evalTime > w.notAfter {
			inert++
			continue
		}
		endorsements := 0
		for signer := range signers[w.id] {
			if custodians[signer] {
				endorsements++
			}
		}
		if endorsements < quorum {
			inert++
			continue
		}
		if countermanded[w.id] {
			inert++
			continue
		}
		if !authorities[w.issuer] || baseNames[w.issuer] {
			inert++
			continue
		}

		honored++
		switch w.kind {
		case "fingerprint":
			fpSet[w.value] = true
			stmts = append(stmts,
				"INSERT OR IGNORE INTO distrust_fingerprint (fingerprint, source) VALUES ('"+
					w.value+"', 'warrant_honored');")
		case "common_name":
			nameSet[w.value] = true
			stmts = append(stmts,
				"INSERT OR IGNORE INTO distrust_name (common_name, source) VALUES ('"+
					w.value+"', 'warrant_honored');")
		}
	}

	var fps, names []string
	recovered := []string{}
	for f := range fpSet {
		fps = append(fps, f)
		if !postFP[f] {
			recovered = append(recovered, f)
		}
	}
	for n := range nameSet {
		names = append(names, n)
	}
	sort.Strings(fps)
	sort.Strings(names)
	sort.Strings(recovered)

	sqlText := strings.Join(stmts, "\n") + "\n"
	return attest.Distrust{ByFP: fps, ByName: names}, PatchSummary{
		Honored:              honored,
		Inert:                inert,
		RestoredFingerprints: recovered,
		SQL:                  sqlText,
	}
}

func warrantQuorum(dataDir string) int {
	data, err := os.ReadFile(filepath.Join(dataDir, "remediation.policy"))
	if err != nil {
		return 1
	}
	section := ""
	for _, raw := range strings.Split(string(data), "\n") {
		line := strings.TrimSpace(raw)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if strings.HasPrefix(line, "[") && strings.HasSuffix(line, "]") {
			section = line[1 : len(line)-1]
			continue
		}
		if section != "remediation" {
			continue
		}
		key, val, found := strings.Cut(line, "=")
		if !found || strings.TrimSpace(key) != "warrant_quorum" {
			continue
		}
		if n, err := strconv.Atoi(strings.TrimSpace(val)); err == nil {
			return n
		}
	}
	return 1
}

func readEvalTime(dataDir string) string {
	data, err := os.ReadFile(filepath.Join(dataDir, "eval_time.txt"))
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(data))
}

func custodianSet(dbPath string) map[string]bool {
	out := map[string]bool{}
	for _, row := range sqliteQuery(dbPath,
		`SELECT signer_id FROM authorized_signer WHERE role = 'custodian'`) {
		out[row[0]] = true
	}
	return out
}

func distinctSigners(dbPath string) map[string]map[string]bool {
	out := map[string]map[string]bool{}
	for _, row := range sqliteQuery(dbPath,
		`SELECT warrant_id, signer_id FROM warrant_countersignature`) {
		if out[row[0]] == nil {
			out[row[0]] = map[string]bool{}
		}
		out[row[0]][row[1]] = true
	}
	return out
}

func countermandSet(dbPath string) map[string]bool {
	out := map[string]bool{}
	for _, row := range sqliteQuery(dbPath, `SELECT warrant_id FROM warrant_countermand`) {
		out[row[0]] = true
	}
	return out
}

func authorityCNs(dataDir string) map[string]bool {
	out := map[string]bool{}
	entries, err := os.ReadDir(filepath.Join(dataDir, "authorities"))
	if err != nil {
		return out
	}
	for _, e := range entries {
		if !strings.HasSuffix(e.Name(), ".pem") {
			continue
		}
		raw, err := os.ReadFile(filepath.Join(dataDir, "authorities", e.Name()))
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
		out[cert.Subject.CommonName] = true
	}
	return out
}

func sqliteQuery(dbPath, query string) [][]string {
	cmd := exec.Command("sqlite3", dbPath, query)
	cmd.Env = append(os.Environ(), "SQLITE_HEADER=off")
	out, err := cmd.Output()
	if err != nil {
		panic(err)
	}
	text := strings.TrimSpace(string(out))
	if text == "" {
		return nil
	}
	var rows [][]string
	for _, line := range strings.Split(text, "\n") {
		rows = append(rows, strings.Split(line, "|"))
	}
	return rows
}
GOEOF

cat > internal/policy/roundtrip.go <<'GOEOF'
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

func WriteRejected(outDir string, doc *Document) error {
	var lines []string
	lines = append(lines, doc.Lines...)
	lines = append(lines, "[remediation_audit]")
	lines = append(lines, "status=rejected")
	lines = append(lines, "reason=contradictory_known_fields")
	return os.WriteFile(filepath.Join(outDir, "remediated.policy"), []byte(strings.Join(lines, "\n")+"\n"), 0644)
}

func WriteRoundtrip(outDir string, doc *Document) error {
	return os.WriteFile(filepath.Join(outDir, "remediated.policy"), []byte(strings.Join(doc.Lines, "\n")+"\n"), 0644)
}
GOEOF

cat > internal/provenance/join.go <<'GOEOF'
package provenance

import (
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"

	"trustremediator/internal/attest"
)

func accessMinute(ts string) string {
	if len(ts) >= 16 {
		return ts[:16]
	}
	return ts
}

func joinKey(certFP, serviceID, accessTS string) string {
	raw := certFP + ":" + serviceID + ":" + accessMinute(accessTS)
	h := sha256.Sum256([]byte(raw))
	return hex.EncodeToString(h[:])
}

type fsRec struct {
	CertFP    string
	ServiceID string
	AccessTS  string
}

type dbRec struct {
	CertFP    string
	ServiceID string
	AccessTS  string
}

func parseJournalLine(line string) fsRec {
	parts := strings.Fields(line)
	kv := map[string]string{}
	for _, p := range parts[1:] {
		if k, v, ok := strings.Cut(p, "="); ok {
			kv[k] = v
		}
	}
	return fsRec{
		CertFP:    kv["cert_fp"],
		ServiceID: kv["service"],
		AccessTS:  kv["ts"],
	}
}

func Build(dataDir string) []attest.ProvEntry {
	var fsRecs []fsRec
	fh, err := os.Open(filepath.Join(dataDir, "access", "access.journal"))
	if err != nil {
		panic(err)
	}
	defer fh.Close()
	sc := bufio.NewScanner(fh)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || !strings.HasPrefix(line, "ACCESS") {
			continue
		}
		fsRecs = append(fsRecs, parseJournalLine(line))
	}

	dbRows := sqliteQuery(filepath.Join(dataDir, "access", "access_audit.db"),
		`SELECT cert_fp, service_id, access_ts FROM access_records`)
	var dbRecs []dbRec
	for _, row := range dbRows {
		dbRecs = append(dbRecs, dbRec{CertFP: row[0], ServiceID: row[1], AccessTS: row[2]})
	}

	type tuple struct {
		cert, svc, minute string
	}
	fsKeys := map[tuple]string{}
	dbKeys := map[tuple]string{}
	for _, r := range fsRecs {
		minute := accessMinute(r.AccessTS)
		t := tuple{r.CertFP, r.ServiceID, minute}
		fsKeys[t] = joinKey(r.CertFP, r.ServiceID, r.AccessTS)
	}
	for _, r := range dbRecs {
		minute := accessMinute(r.AccessTS)
		t := tuple{r.CertFP, r.ServiceID, minute}
		dbKeys[t] = joinKey(r.CertFP, r.ServiceID, r.AccessTS)
	}

	all := map[tuple]bool{}
	for t := range fsKeys {
		all[t] = true
	}
	for t := range dbKeys {
		all[t] = true
	}
	var tuples []tuple
	for t := range all {
		tuples = append(tuples, t)
	}
	sort.Slice(tuples, func(i, j int) bool {
		if tuples[i].cert != tuples[j].cert {
			return tuples[i].cert < tuples[j].cert
		}
		if tuples[i].svc != tuples[j].svc {
			return tuples[i].svc < tuples[j].svc
		}
		return tuples[i].minute < tuples[j].minute
	})

	var out []attest.ProvEntry
	for _, t := range tuples {
		_, inFS := fsKeys[t]
		_, inDB := dbKeys[t]
		status := "joined"
		if inFS && !inDB {
			status = "fs_only"
		} else if !inFS && inDB {
			status = "db_only"
		}
		jk := fsKeys[t]
		if jk == "" {
			jk = dbKeys[t]
		}
		out = append(out, attest.ProvEntry{
			CertFP: t.cert, ServiceID: t.svc, AccessMinute: t.minute,
			JoinKey: jk, JoinStatus: status,
		})
	}
	return out
}

func sqliteQuery(dbPath, query string) [][]string {
	cmd := exec.Command("sqlite3", dbPath, query)
	cmd.Env = append(os.Environ(), "SQLITE_HEADER=off")
	out, err := cmd.Output()
	if err != nil {
		panic(err)
	}
	text := strings.TrimSpace(string(out))
	if text == "" {
		return nil
	}
	var rows [][]string
	for _, line := range strings.Split(text, "\n") {
		rows = append(rows, strings.Split(line, "|"))
	}
	return rows
}
GOEOF

cat > internal/pki/validate.go <<'GOEOF'
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

func ValidateCerts(dataDir string, eff attest.Distrust) []attest.Verdict {
	_, trustedMap, err := truststore.Load(dataDir)
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
GOEOF

make
touch build/trust_attest
./build/trust_attest --incident /app/data --write /app/output
