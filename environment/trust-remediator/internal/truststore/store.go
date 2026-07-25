package truststore

import (
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"

	"trustremediator/internal/attest"
)

func Load(dataDir string) (attest.Distrust, map[string]bool, error) {
	dbPath := filepath.Join(dataDir, "trust_store.db")
	fps, err := queryColumn(dbPath, "SELECT fingerprint FROM distrust_fingerprint ORDER BY fingerprint")
	if err != nil {
		return attest.Distrust{}, nil, err
	}
	names, err := queryColumn(dbPath, "SELECT common_name FROM distrust_name ORDER BY common_name")
	if err != nil {
		return attest.Distrust{}, nil, err
	}
	trustedRows, err := queryColumn(dbPath, "SELECT fingerprint FROM trusted_roots")
	if err != nil {
		return attest.Distrust{}, nil, err
	}
	trusted := map[string]bool{}
	for _, f := range trustedRows {
		trusted[f] = true
	}
	return attest.Distrust{ByFP: fps, ByName: names}, trusted, nil
}

func queryColumn(dbPath, query string) ([]string, error) {
	rows, err := sqliteQuery(dbPath, query)
	if err != nil {
		return nil, err
	}
	var out []string
	for _, row := range rows {
		if len(row) > 0 {
			out = append(out, row[0])
		}
	}
	sort.Strings(out)
	return out, nil
}

func sqliteQuery(dbPath, query string) ([][]string, error) {
	cmd := exec.Command("sqlite3", dbPath, query)
	cmd.Env = append(os.Environ(), "SQLITE_HEADER=off")
	out, err := cmd.Output()
	if err != nil {
		return nil, err
	}
	text := strings.TrimSpace(string(out))
	if text == "" {
		return nil, nil
	}
	var rows [][]string
	for _, line := range strings.Split(text, "\n") {
		rows = append(rows, strings.Split(line, "|"))
	}
	return rows, nil
}
