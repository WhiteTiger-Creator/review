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
