package trail

import (
	"database/sql"
	"embed"
	"fmt"
	"os"
	"path/filepath"
	"sort"

	_ "modernc.org/sqlite"

	"migrator/internal/register"
	"migrator/internal/topology"
	"migrator/internal/precedence"
	"migrator/internal/federation"
	"migrator/internal/policy"
)

//go:embed sql/*.sql
var sqlFiles embed.FS

type Writer struct {
	db *sql.DB
}

func NewWriter(path string) (*Writer, error) {
	_ = os.Remove(path)
	db, err := sql.Open("sqlite", path)
	if err != nil {
		return nil, err
	}
	w := &Writer{db: db}
	if err := w.initSchema(); err != nil {
		return nil, err
	}
	return w, nil
}

func (w *Writer) Close() error { return w.db.Close() }

func (w *Writer) initSchema() error {
	for _, name := range []string{"001_schema.sql", "002_recursive_assertions.sql", "003_report_views.sql"} {
		raw, err := sqlFiles.ReadFile(filepath.Join("sql", name))
		if err != nil {
			return err
		}
		if _, err := w.db.Exec(string(raw)); err != nil {
			return err
		}
	}
	return nil
}

func (w *Writer) BeginRun() (int64, error) {
	res, err := w.db.Exec(`INSERT INTO migration_run(status, started_at) VALUES ('STARTED', datetime('now'))`)
	if err != nil {
		return 0, err
	}
	return res.LastInsertId()
}

func (w *Writer) FailRun(id int64, msg string) error {
	_, err := w.db.Exec(`UPDATE migration_run SET status='FAILED', error=? WHERE id=?`, msg, id)
	return err
}

func (w *Writer) CompleteRun(id int64) error {
	_, err := w.db.Exec(`UPDATE migration_run SET status='COMPLETE', completed_at=datetime('now') WHERE id=?`, id)
	return err
}

func (w *Writer) RecordEvidence(runID int64, g *topology.Graph, leg *precedence.Legacy, decisions map[string]register.Decision, disc *federation.Discovery, keys []federation.Key, bundle *policy.Bundle) error {
	tx, err := w.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()
	for _, e := range g.Edges {
		_, err := tx.Exec(`INSERT INTO graph_edge(run_id, edge_key, source, target, environment, method, path, authz_scope, denied) VALUES (?,?,?,?,?,?,?,?,?)`,
			runID, topology.EdgeKey(e), e.Source, e.Target, e.Environment, e.Method, e.Path, e.AuthzScope, e.Denied)
		if err != nil {
			return err
		}
	}
	_, err = tx.Exec(`INSERT OR REPLACE INTO discovery_snapshot(id, run_id, issuer, jwks_uri, fetch_url, semantic_url) VALUES (1,?,?,?,?,?)`,
		runID, disc.Issuer, disc.JWKSURI, disc.FetchURL, disc.SemanticDiscoveryURL)
	if err != nil {
		return err
	}
	for _, k := range keys {
		_, err := tx.Exec(`INSERT INTO jwk_evidence(run_id, kid, kty, alg, issuer) VALUES (?,?,?,?,?)`,
			runID, k.KID, k.KTY, k.ALG, disc.Issuer)
		if err != nil {
			return err
		}
	}
	for _, ep := range bundle.Edges {
		_, err := tx.Exec(`INSERT INTO policy_edge(run_id, edge_key, action, issuer, audiences, algorithms) VALUES (?,?,?,?,?,?)`,
			runID, ep.EdgeID, ep.Action, ep.Issuer, join(ep.Audiences), join(ep.Algorithms))
		if err != nil {
			return err
		}
	}
	_ = leg
	_ = decisions
	return tx.Commit()
}

func (w *Writer) RunRecursiveChecks(runID int64) error {
	var uncovered int
	row := w.db.QueryRow(`SELECT COUNT(*) FROM coverage_gaps WHERE run_id = ?`, runID)
	if err := row.Scan(&uncovered); err != nil {
		return err
	}
	if uncovered > 0 {
		return fmt.Errorf("recursive coverage found %d gaps", uncovered)
	}
	return nil
}

func join(items []string) string {
	cp := append([]string{}, items...)
	sort.Strings(cp)
	out := ""
	for i, s := range cp {
		if i > 0 {
			out += ","
		}
		out += s
	}
	return out
}
