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
	signatureRows := countersignatureRows(dbPath)
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

		if w.notBefore > evalTime || evalTime > w.notAfter {
			inert++
			continue
		}
		if len(signatureRows[w.id]) < quorum {
			inert++
			continue
		}
		if !authorities[w.issuer] || baseNames[w.issuer] {
			inert++
			continue
		}

		switch w.kind {
		case "fingerprint":
			honored++
		case "common_name":
			nameSet[w.value] = true
			honored++
			stmts = append(stmts,
				"INSERT OR IGNORE INTO distrust_name (common_name, source) VALUES ('"+
					w.value+"', 'warrant_honored');")
		default:
			inert++
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

func countersignatureRows(dbPath string) map[string][]string {
	out := map[string][]string{}
	for _, row := range sqliteQuery(dbPath,
		`SELECT warrant_id, signer_id FROM warrant_countersignature`) {
		out[row[0]] = append(out[row[0]], row[1])
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
