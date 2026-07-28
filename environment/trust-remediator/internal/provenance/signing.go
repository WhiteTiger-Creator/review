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
	return term[0] <= eventTS
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
