#!/bin/bash
set -euo pipefail

cd /app/trust-remediator
mkdir -p build /app/output

mkdir -p internal/authority
cat > internal/authority/cascade.go <<'GOEOF'
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
GOEOF

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
	"trustremediator/internal/authority"
)

type PatchSummary struct {
	Honored              int
	Inert                int
	RestoredFingerprints []string
	ContainmentNames     []string
	SQL                  string
}

// WithContainment folds the exposure containment set into the patch, appending
// its rows after the warrant rows in common-name order.
func WithContainment(s PatchSummary, names []string) PatchSummary {
	s.ContainmentNames = append([]string{}, names...)
	sort.Strings(s.ContainmentNames)
	var b strings.Builder
	b.WriteString(s.SQL)
	for _, n := range s.ContainmentNames {
		b.WriteString("INSERT OR IGNORE INTO distrust_name (common_name, source) VALUES ('" +
			n + "', 'exposure_containment');\n")
	}
	s.SQL = b.String()
	return s
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
	endorsers := countingEndorsers(dbPath, custodians)
	countermanded := countermandSet(dbPath)
	authorities := authorityCNs(dataDir)
	cascaded := authority.Set(dataDir, base.ByName)

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
		if len(endorsers[w.id]) < quorum {
			inert++
			continue
		}
		if countermanded[w.id] {
			inert++
			continue
		}
		if !authorities[w.issuer] || cascaded[w.issuer] {
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

type custodianTerm struct {
	from  string
	until string
}

func custodianSet(dbPath string) map[string]custodianTerm {
	out := map[string]custodianTerm{}
	for _, row := range sqliteQuery(dbPath,
		`SELECT signer_id, role_from, role_until FROM authorized_signer WHERE role = 'custodian'`) {
		out[row[0]] = custodianTerm{from: row[1], until: row[2]}
	}
	return out
}

// countingEndorsers maps a warrant to the distinct signers whose endorsement
// counts, meaning the signer was rostered as a custodian at the moment it
// signed. The term is compared against signed_at, never against eval_time.
func countingEndorsers(dbPath string, custodians map[string]custodianTerm) map[string]map[string]bool {
	out := map[string]map[string]bool{}
	for _, row := range sqliteQuery(dbPath,
		`SELECT warrant_id, signer_id, signed_at FROM warrant_countersignature`) {
		warrantID, signer, signedAt := row[0], row[1], row[2]
		term, rostered := custodians[signer]
		if !rostered || signedAt < term.from || signedAt > term.until {
			continue
		}
		if out[warrantID] == nil {
			out[warrantID] = map[string]bool{}
		}
		out[warrantID][signer] = true
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
	"trustremediator/internal/authority"
	"trustremediator/internal/truststore"
)

var rank = map[string]int{"acceptable": 0, "not_yet_valid": 1, "expired": 2, "name_constraint": 3, "revoked": 4}

// PathInfo is one anchored certification path, described by the subject common
// names of its members with the leaf first.
type PathInfo struct {
	Members []string
	// Sound reports whether the path would be accepted on its own merits,
	// ignoring distrust entirely.
	Sound bool
}

// AnchoredPaths returns, per leaf common name, every anchored path that leaf has.
func AnchoredPaths(dataDir string) map[string][]PathInfo {
	authorities := loadDir(filepath.Join(dataDir, "authorities"))
	leaves := loadDir(filepath.Join(dataDir, "leaves"))
	_, trustedMap, err := truststore.Load(dataDir)
	if err != nil {
		panic(err)
	}
	tb, err := os.ReadFile(filepath.Join(dataDir, "eval_time.txt"))
	if err != nil {
		panic(err)
	}
	T, err := time.Parse(time.RFC3339, strings.TrimSpace(string(tb)))
	if err != nil {
		panic(err)
	}

	out := map[string][]PathInfo{}
	for _, leaf := range leaves {
		var all [][]*x509.Certificate
		enumeratePaths(leaf, []*x509.Certificate{leaf}, map[string]bool{cn(leaf): true}, &all, authorities)
		infos := []PathInfo{}
		for _, p := range all {
			if !trustedMap[fp(p[len(p)-1])] {
				continue
			}
			names := make([]string, 0, len(p))
			for _, m := range p {
				names = append(names, cn(m))
			}
			infos = append(infos, PathInfo{Members: names, Sound: soundPath(p, T)})
		}
		out[cn(leaf)] = infos
	}
	return out
}

func soundPath(chain []*x509.Certificate, T time.Time) bool {
	if nameViolation(chain) != nil {
		return false
	}
	for _, m := range chain {
		if m.NotAfter.Before(T) || m.NotBefore.After(T) {
			return false
		}
	}
	return true
}

func enumeratePaths(cur *x509.Certificate, chain []*x509.Certificate, seen map[string]bool,
	out *[][]*x509.Certificate, authorities []*x509.Certificate) {
	if selfSigned(cur) {
		cp := make([]*x509.Certificate, len(chain))
		copy(cp, chain)
		*out = append(*out, cp)
		return
	}
	for _, a := range authorities {
		if !bytes.Equal(a.RawSubject, cur.RawIssuer) || !verify(cur, a) || seen[cn(a)] {
			continue
		}
		ns := map[string]bool{}
		for k := range seen {
			ns[k] = true
		}
		ns[cn(a)] = true
		enumeratePaths(a, append(append([]*x509.Certificate{}, chain...), a), ns, out, authorities)
	}
}

func nameViolation(chain []*x509.Certificate) *int {
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
		for _, s := range sans {
			for _, e := range ca.ExcludedDNSDomains {
				if dnsMatch(e, s) {
					bad = true
				}
			}
		}
		if bad && best == nil {
			d := i
			best = &d
		}
	}
	return best
}

func ValidateCerts(dataDir string, eff attest.Distrust, containment []string) []attest.Verdict {
	postMigration, trustedMap, err := truststore.Load(dataDir)
	if err != nil {
		panic(err)
	}
	cascaded := authority.Set(dataDir, append(append([]string{}, postMigration.ByName...), containment...))
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
			if byFP[fp(m)] || byName[cn(m)] || cascaded[cn(m)] {
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

mkdir -p internal/exposure
cat > internal/exposure/contain.go <<'GOEOF'
package exposure

import (
	"os"
	"path/filepath"
	"sort"
	"strings"

	"trustremediator/internal/attest"
	"trustremediator/internal/authority"
	"trustremediator/internal/pki"
	"trustremediator/internal/provenance"
	"trustremediator/internal/truststore"
)

type Subject struct {
	Incident    string
	Name        string
	Disposition string
}

func Load(dataDir string) []Subject {
	raw, err := os.ReadFile(filepath.Join(dataDir, "exposure.tsv"))
	if err != nil {
		panic(err)
	}
	var subs []Subject
	for i, line := range strings.Split(strings.TrimRight(string(raw), "\n"), "\n") {
		if i == 0 {
			continue
		}
		cols := strings.Split(line, "\t")
		if len(cols) != 3 {
			panic("bad exposure row: " + line)
		}
		subs = append(subs, Subject{Incident: cols[0], Name: cols[1], Disposition: cols[2]})
	}
	return subs
}

// Select returns the smallest containment set, and among the smallest the one
// that comes first in common-name order.
func Select(dataDir string, eff attest.Distrust) []string {
	subs := Load(dataDir)
	paths := pki.AnchoredPaths(dataDir)

	post, _, err := truststore.Load(dataDir)
	if err != nil {
		panic(err)
	}
	standing := authority.Set(dataDir, post.ByName)
	for _, n := range eff.ByName {
		standing[n] = true
	}

	// A path only needs cutting, and only counts as a survivor, while it is live.
	live := map[string][][]string{}
	for _, s := range subs {
		for _, p := range paths[s.Name] {
			if !p.Sound {
				continue
			}
			tainted := false
			for _, m := range p.Members {
				if standing[m] {
					tainted = true
					break
				}
			}
			if !tainted {
				live[s.Name] = append(live[s.Name], p.Members)
			}
		}
	}

	var contain, preserve []string
	compromised := map[string]bool{}
	for _, cn := range provenance.CompromisedLeaves(dataDir) {
		compromised[cn] = true
	}
	for _, s := range subs {
		switch s.Disposition {
		case "contain":
			contain = append(contain, s.Name)
		case "preserve":
			if !compromised[s.Name] {
				preserve = append(preserve, s.Name)
			}
		}
	}
	for cn := range compromised {
		contain = append(contain, cn)
	}
	sort.Strings(contain)
	contain = dedupeSorted(contain)

	for _, name := range contain {
		if _, ok := live[name]; ok {
			continue
		}
		for _, p := range paths[name] {
			if !p.Sound {
				continue
			}
			tainted := false
			for _, m := range p.Members {
				if standing[m] {
					tainted = true
					break
				}
			}
			if !tainted {
				live[name] = append(live[name], p.Members)
			}
		}
	}

	edges := authority.Edges(dataDir)
	candidates := authority.Names(dataDir)

	feasible := func(set []string) bool {
		cascaded := closure(edges, set)
		for _, name := range contain {
			for _, p := range live[name] {
				if !hits(cascaded, p) {
					return false
				}
			}
		}
		for _, name := range preserve {
			survived := false
			for _, p := range live[name] {
				if !hits(cascaded, p) {
					survived = true
					break
				}
			}
			if !survived {
				return false
			}
		}
		return true
	}

	// Smallest first, and within a size the first combination in name order,
	// which is what makes the answer unique.
	for size := 0; size <= len(candidates); size++ {
		var found []string
		combinations(candidates, size, func(set []string) bool {
			if feasible(set) {
				found = append([]string{}, set...)
				return true
			}
			return false
		})
		if found != nil {
			return found
		}
	}
	panic("no containment set satisfies the incident")
}

func closure(edges map[string][]string, seed []string) map[string]bool {
	out := map[string]bool{}
	stack := []string{}
	for _, s := range seed {
		if !out[s] {
			out[s] = true
			stack = append(stack, s)
		}
	}
	for len(stack) > 0 {
		cur := stack[len(stack)-1]
		stack = stack[:len(stack)-1]
		for _, kid := range edges[cur] {
			if !out[kid] {
				out[kid] = true
				stack = append(stack, kid)
			}
		}
	}
	return out
}

func hits(set map[string]bool, path []string) bool {
	for _, m := range path {
		if set[m] {
			return true
		}
	}
	return false
}

// combinations walks size-sized subsets in ascending index order, so the first
// one accepted by stop is the first in name order.
func combinations(items []string, size int, stop func([]string) bool) {
	cur := make([]string, size)
	var rec func(start, depth int) bool
	rec = func(start, depth int) bool {
		if depth == size {
			return stop(cur)
		}
		for i := start; i <= len(items)-(size-depth); i++ {
			cur[depth] = items[i]
			if rec(i+1, depth+1) {
				return true
			}
		}
		return false
	}
	rec(0, 0)
}

func dedupeSorted(items []string) []string {
	if len(items) == 0 {
		return items
	}
	sort.Strings(items)
	out := []string{items[0]}
	for _, it := range items[1:] {
		if it != out[len(out)-1] {
			out = append(out, it)
		}
	}
	return out
}
GOEOF

cat > internal/provenance/signing.go <<'GOEOF'
package provenance

import (
	"bufio"
	"crypto/sha256"
	"crypto/x509"
	"encoding/hex"
	"encoding/pem"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"trustremediator/internal/attest"
)

type signEvent struct {
	CertFP   string
	SignerID string
	EventTS  string
}

func journalPaths(dataDir string) []string {
	paths := []string{filepath.Join(dataDir, "access", "access.journal")}
	held := filepath.Join(dataDir, "access", "held_out.journal")
	if _, err := os.Stat(held); err == nil {
		paths = append(paths, held)
	}
	return paths
}

func parseSignLine(line string) signEvent {
	parts := strings.Fields(line)
	kv := map[string]string{}
	for _, p := range parts[1:] {
		if k, v, ok := strings.Cut(p, "="); ok {
			kv[k] = v
		}
	}
	return signEvent{CertFP: kv["cert_fp"], SignerID: kv["signer"], EventTS: kv["ts"]}
}

func loadSignEvents(dataDir string) []signEvent {
	var out []signEvent
	for _, path := range journalPaths(dataDir) {
		fh, err := os.Open(path)
		if err != nil {
			panic(err)
		}
		sc := bufio.NewScanner(fh)
		for sc.Scan() {
			line := strings.TrimSpace(sc.Text())
			if line == "" || !strings.HasPrefix(line, "SIGN") {
				continue
			}
			out = append(out, parseSignLine(line))
		}
		fh.Close()
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].CertFP != out[j].CertFP {
			return out[i].CertFP < out[j].CertFP
		}
		if out[i].SignerID != out[j].SignerID {
			return out[i].SignerID < out[j].SignerID
		}
		return out[i].EventTS < out[j].EventTS
	})
	return out
}

func reconcileKey(certFP, signerID, eventTS string) string {
	raw := certFP + ":" + signerID + ":" + eventTS
	h := sha256.Sum256([]byte(raw))
	return hex.EncodeToString(h[:])
}

func custodianTerms(dataDir string) map[string][2]string {
	out := map[string][2]string{}
	for _, row := range sqliteQuery(filepath.Join(dataDir, "warrants", "warrants.db"),
		`SELECT signer_id, role_from, role_until FROM authorized_signer WHERE role = 'custodian'`) {
		out[row[0]] = [2]string{row[1], row[2]}
	}
	return out
}

func inWindow(signerID, eventTS string, terms map[string][2]string) bool {
	term, ok := terms[signerID]
	if !ok {
		return false
	}
	return term[0] <= eventTS && eventTS <= term[1]
}

func leafFPToCN(dataDir string) map[string]string {
	out := map[string]string{}
	dir := filepath.Join(dataDir, "leaves")
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
		h := sha256.Sum256(cert.Raw)
		fp := hex.EncodeToString(h[:])
		out[fp] = cert.Subject.CommonName
	}
	return out
}

func SigningReconcile(dataDir string) ([]attest.SignEntry, string, []string) {
	terms := custodianTerms(dataDir)
	events := loadSignEvents(dataDir)
	fpToCN := leafFPToCN(dataDir)
	compromised := map[string]bool{}
	var entries []attest.SignEntry
	h := sha256.New()
	for _, ev := range events {
		rk := reconcileKey(ev.CertFP, ev.SignerID, ev.EventTS)
		status := "in_window"
		if !inWindow(ev.SignerID, ev.EventTS, terms) {
			status = "out_of_window"
			if cn, ok := fpToCN[ev.CertFP]; ok {
				compromised[cn] = true
			}
		}
		_, _ = h.Write([]byte(rk))
		entries = append(entries, attest.SignEntry{
			CertFP: ev.CertFP, SignerID: ev.SignerID, EventTS: ev.EventTS,
			ReconcileKey: rk, ReconcileStatus: status,
		})
	}
	digest := hex.EncodeToString(h.Sum(nil))
	var leaves []string
	for cn := range compromised {
		leaves = append(leaves, cn)
	}
	sort.Strings(leaves)
	return entries, digest, leaves
}

func CompromisedLeaves(dataDir string) []string {
	_, _, leaves := SigningReconcile(dataDir)
	return leaves
}
GOEOF

cat > internal/attest/types.go <<'GOEOF'
package attest

type Distrust struct {
	ByFP   []string
	ByName []string
}

type Verdict struct {
	Leaf            string
	Decision        string
	Reason          string
	SelectedPath    []string
	PathsConsidered int
	ConstraintDepth *int
	TaintedMembers  []string
}

type ProvEntry struct {
	CertFP       string
	ServiceID    string
	AccessMinute string
	JoinKey      string
	JoinStatus   string
}

type SignEntry struct {
	CertFP          string
	SignerID        string
	EventTS         string
	ReconcileKey    string
	ReconcileStatus string
}

func VerdictMap(v Verdict) map[string]interface{} {
	return map[string]interface{}{
		"constraint_violation_depth": v.ConstraintDepth,
		"decision":                   v.Decision,
		"leaf":                       v.Leaf,
		"paths_considered":           v.PathsConsidered,
		"reason":                     v.Reason,
		"selected_path":              v.SelectedPath,
		"tainted_members":            v.TaintedMembers,
	}
}

func ProvMap(p ProvEntry) map[string]interface{} {
	return map[string]interface{}{
		"access_minute": p.AccessMinute,
		"cert_fp":       p.CertFP,
		"join_key":      p.JoinKey,
		"join_status":   p.JoinStatus,
		"service_id":    p.ServiceID,
	}
}

func VerdictSlice(items []Verdict) []map[string]interface{} {
	out := make([]map[string]interface{}, len(items))
	for i, v := range items {
		out[i] = VerdictMap(v)
	}
	return out
}

func ProvSlice(items []ProvEntry) []map[string]interface{} {
	out := make([]map[string]interface{}, len(items))
	for i, p := range items {
		out[i] = ProvMap(p)
	}
	return out
}
GOEOF

cat > internal/output/write.go <<'GOEOF'
package output

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"trustremediator/internal/attest"
	"trustremediator/internal/warrant"
)

func CopyAndApplyPatch(dataDir, outDir, sql string) error {
	src := filepath.Join(dataDir, "trust_store.db")
	dst := filepath.Join(outDir, "remediated_trust_store.db")
	in, err := os.ReadFile(src)
	if err != nil {
		return err
	}
	if err := os.WriteFile(dst, in, 0644); err != nil {
		return err
	}
	if strings.TrimSpace(sql) == "" || sql == "-- trust store remediation patch\n" {
		return nil
	}
	tmpSQL := filepath.Join(outDir, ".apply.sql")
	if err := os.WriteFile(tmpSQL, []byte(sql), 0644); err != nil {
		return err
	}
	cmd := exec.Command("sqlite3", dst, fmt.Sprintf(".read %s", tmpSQL))
	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("apply patch: %v: %s", err, out)
	}
	_ = os.Remove(tmpSQL)
	return nil
}

func WriteSQL(outDir, sql string) error {
	return os.WriteFile(filepath.Join(outDir, "remediation.sql"), []byte(sql), 0644)
}

func WriteAccessTSV(outDir string, entries []attest.ProvEntry) error {
	var b strings.Builder
	b.WriteString("cert_fp\tservice_id\taccess_minute\tjoin_key\tjoin_status\n")
	for _, e := range entries {
		fmt.Fprintf(&b, "%s\t%s\t%s\t%s\t%s\n", e.CertFP, e.ServiceID, e.AccessMinute, e.JoinKey, e.JoinStatus)
	}
	return os.WriteFile(filepath.Join(outDir, "access_evidence.tsv"), []byte(b.String()), 0644)
}

func WriteSigningTSV(outDir string, entries []attest.SignEntry) error {
	var b strings.Builder
	b.WriteString("cert_fp\tsigner_id\tevent_ts\treconcile_key\treconcile_status\n")
	for _, e := range entries {
		fmt.Fprintf(&b, "%s\t%s\t%s\t%s\t%s\n",
			e.CertFP, e.SignerID, e.EventTS, e.ReconcileKey, e.ReconcileStatus)
	}
	return os.WriteFile(filepath.Join(outDir, "signing_reconcile.tsv"), []byte(b.String()), 0644)
}

func WriteCertTSV(outDir string, verdicts []attest.Verdict) error {
	var b strings.Builder
	b.WriteString("leaf\tdecision\treason\tpaths_considered\tconstraint_depth\ttainted_members\tselected_path\n")
	for _, v := range verdicts {
		depth := ""
		if v.ConstraintDepth != nil {
			depth = fmt.Sprintf("%d", *v.ConstraintDepth)
		}
		tm := strings.Join(v.TaintedMembers, ",")
		sp := strings.Join(v.SelectedPath, ",")
		fmt.Fprintf(&b, "%s\t%s\t%s\t%d\t%s\t%s\t%s\n",
			v.Leaf, v.Decision, v.Reason, v.PathsConsidered, depth, tm, sp)
	}
	return os.WriteFile(filepath.Join(outDir, "certificate_decisions.tsv"), []byte(b.String()), 0644)
}

func WriteReceipt(outDir string, summary warrant.PatchSummary, journalDigest string, compromised []string) error {
	sqlBytes, _ := os.ReadFile(filepath.Join(outDir, "remediation.sql"))
	accessBytes, _ := os.ReadFile(filepath.Join(outDir, "access_evidence.tsv"))
	signBytes, _ := os.ReadFile(filepath.Join(outDir, "signing_reconcile.tsv"))
	certBytes, _ := os.ReadFile(filepath.Join(outDir, "certificate_decisions.tsv"))
	h := sha256.New()
	for _, chunk := range [][]byte{sqlBytes, accessBytes, signBytes, certBytes} {
		_, _ = h.Write(chunk)
	}
	digest := hex.EncodeToString(h.Sum(nil))
	restored := strings.Join(summary.RestoredFingerprints, ",")
	comp := strings.Join(compromised, ",")
	var b strings.Builder
	fmt.Fprintf(&b, "warrants_honored=%d\n", summary.Honored)
	fmt.Fprintf(&b, "warrants_inert=%d\n", summary.Inert)
	fmt.Fprintf(&b, "restored_fingerprints=%s\n", restored)
	fmt.Fprintf(&b, "containment_names=%s\n", strings.Join(summary.ContainmentNames, ","))
	fmt.Fprintf(&b, "containment_size=%d\n", len(summary.ContainmentNames))
	fmt.Fprintf(&b, "journal_reconcile_digest=%s\n", journalDigest)
	fmt.Fprintf(&b, "compromised_leaves=%s\n", comp)
	fmt.Fprintf(&b, "artifact_digest=%s\n", digest)
	return os.WriteFile(filepath.Join(outDir, "audit_receipt.txt"), []byte(b.String()), 0644)
}

func FileDigest(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}
GOEOF

cat > cmd/trust-attest/main.go <<'GOEOF'
package main

import (
	"flag"
	"fmt"
	"os"
	"sort"

	"trustremediator/internal/exposure"
	"trustremediator/internal/output"
	"trustremediator/internal/pki"
	"trustremediator/internal/policy"
	"trustremediator/internal/provenance"
	"trustremediator/internal/truststore"
	"trustremediator/internal/warrant"
)

func main() {
	incident := flag.String("incident", "", "incident evidence directory")
	writeDir := flag.String("write", "", "output directory")
	flag.Parse()
	if *incident == "" || *writeDir == "" {
		fmt.Fprintf(os.Stderr, "usage: trust_attest --incident <dir> --write <dir>\n")
		os.Exit(1)
	}
	dataDir := *incident
	outDir := *writeDir
	if err := os.MkdirAll(outDir, 0755); err != nil {
		panic(err)
	}

	policyDoc, err := policy.Load(dataDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "read policy: %v\n", err)
		os.Exit(1)
	}

	minD, maxD, perr := policy.ChainDepths(policyDoc)
	if perr != nil {
		_ = policy.WriteRejected(outDir, policyDoc)
		os.Exit(2)
	}
	if minD > maxD {
		_ = policy.WriteRejected(outDir, policyDoc)
		os.Exit(2)
	}

	base, _, err := truststore.Load(dataDir)
	if err != nil {
		panic(err)
	}

	eff, patchSummary := warrant.BuildPatch(dataDir, base)
	signEntries, journalDigest, compromised := provenance.SigningReconcile(dataDir)
	contained := exposure.Select(dataDir, eff)
	patchSummary = warrant.WithContainment(patchSummary, contained)
	eff.ByName = append(eff.ByName, contained...)
	sort.Strings(eff.ByName)

	prov := provenance.Build(dataDir)
	verdicts := pki.ValidateCerts(dataDir, eff, contained)

	if err := policy.WriteRoundtrip(outDir, policyDoc); err != nil {
		panic(err)
	}
	if err := output.WriteSQL(outDir, patchSummary.SQL); err != nil {
		panic(err)
	}
	if err := output.CopyAndApplyPatch(dataDir, outDir, patchSummary.SQL); err != nil {
		panic(err)
	}
	if err := output.WriteAccessTSV(outDir, prov); err != nil {
		panic(err)
	}
	if err := output.WriteSigningTSV(outDir, signEntries); err != nil {
		panic(err)
	}
	if err := output.WriteCertTSV(outDir, verdicts); err != nil {
		panic(err)
	}
	if err := output.WriteReceipt(outDir, patchSummary, journalDigest, compromised); err != nil {
		panic(err)
	}
}
GOEOF

make
touch build/trust_attest
./build/trust_attest --incident /app/data --write /app/output
