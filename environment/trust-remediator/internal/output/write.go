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
