package app

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"migrator/internal/trail"
	"migrator/internal/contracts"
	"migrator/internal/register"
	"migrator/internal/topology"
	"migrator/internal/precedence"
	"migrator/internal/federation"
	"migrator/internal/policy"
)

func Run() error {
	cfg := LoadConfig()
	if err := os.MkdirAll(cfg.OutputDir, 0o755); err != nil {
		return err
	}
	if err := os.MkdirAll(cfg.RuntimeDir, 0o755); err != nil {
		return err
	}
	srv, err := federation.StartFixtureServer(federation.TransportConfig{
		OIDCContractRoot:  cfg.OIDCContractRoot,
		OIDCRevision:      cfg.OIDCRevision,
		FixtureListen:     cfg.FixtureListen,
		DiscoveryFetch:    cfg.DiscoveryFetch,
		JWKSFetch:         cfg.JWKSFetch,
		DiscoverySemantic: cfg.DiscoverySemantic,
	})
	if err != nil {
		return err
	}
	defer srv.Close()

	contractData, err := contracts.Load(cfg.CanonicalRoot)
	if err != nil {
		return err
	}
	authority, err := register.LoadAuthority(cfg.AuthorityRoot)
	if err != nil {
		return err
	}
	g, err := topology.Load(cfg.GraphPath, contractData)
	if err != nil {
		return err
	}
	leg, err := precedence.Load(cfg.LegacyPath, contractData)
	if err != nil {
		return err
	}
	decisions, err := register.Load(cfg.DossierRoot, authority, contractData)
	if err != nil {
		return err
	}
	disc, jwks, err := federation.Fetch(federation.TransportConfig{
		OIDCContractRoot:  cfg.OIDCContractRoot,
		OIDCRevision:      cfg.OIDCRevision,
		FixtureListen:     cfg.FixtureListen,
		DiscoveryFetch:    cfg.DiscoveryFetch,
		JWKSFetch:         cfg.JWKSFetch,
		DiscoverySemantic: cfg.DiscoverySemantic,
	})
	if err != nil {
		return err
	}
	keys, algs, err := federation.FilterKeys(jwks, disc, contractData)
	if err != nil {
		return err
	}
	bundle, err := policy.Build(policy.Input{
		Graph: g, Legacy: leg, Decisions: decisions, Discovery: disc, Keys: keys, Algs: algs, Contracts: contractData,
	})
	if err != nil {
		return err
	}
	dbPath := filepath.Join(cfg.OutputDir, "migration-audit.db")
	writer, err := trail.NewWriter(dbPath)
	if err != nil {
		return err
	}
	defer writer.Close()
	runID, err := writer.BeginRun()
	if err != nil {
		return err
	}
	if err := writer.RecordEvidence(runID, g, leg, decisions, disc, keys, bundle); err != nil {
		_ = writer.FailRun(runID, err.Error())
		return err
	}
	if err := error(nil); err != nil {
		_ = writer.FailRun(runID, err.Error())
		return err
	}
	yamlPath := filepath.Join(cfg.OutputDir, "gateway-policy.yaml")
	if err := policy.WriteYAML(yamlPath, bundle); err != nil {
		_ = writer.FailRun(runID, err.Error())
		return err
	}
	summary := map[string]any{
		"schema_version": 1,
		"run_id":         runID,
		"edge_count":     len(bundle.Edges),
		"status":         "complete",
		"revision":       cfg.OIDCRevision,
	}
	sumBytes, _ := json.MarshalIndent(summary, "", "  ")
	sumPath := filepath.Join(cfg.OutputDir, "migration-summary.json")
	if err := os.WriteFile(sumPath, append(sumBytes, '\n'), 0o644); err != nil {
		_ = writer.FailRun(runID, err.Error())
		return err
	}
	if err := writer.CompleteRun(runID); err != nil {
		return err
	}
	fmt.Printf("migration complete: %d edges\n", len(bundle.Edges))
	return nil
}
