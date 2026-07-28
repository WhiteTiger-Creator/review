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
		if endorsers[w.id] < quorum {
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

// countingEndorsers maps a warrant to the number of endorsement rows whose
// signer was rostered as a custodian at the moment it signed. The term is
// compared against signed_at, never against eval_time.
func countingEndorsers(dbPath string, custodians map[string]custodianTerm) map[string]int {
	out := map[string]int{}
	for _, row := range sqliteQuery(dbPath,
		`SELECT warrant_id, signer_id, signed_at FROM warrant_countersignature`) {
		warrantID, signer, signedAt := row[0], row[1], row[2]
		term, rostered := custodians[signer]
		if !rostered || signedAt < term.from || signedAt > term.until {
			continue
		}
		out[warrantID]++
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
