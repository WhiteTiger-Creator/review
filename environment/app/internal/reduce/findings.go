package reduce

import (
	"encoding/json"
	"os"
	"path/filepath"

	"tokenexposure/internal/corpus"
)

func AssembleReport(opaResult map[string]any, events []map[string]any, configDir string) (map[string]any, error) {
	pubPath := filepath.Join(configDir, "publication.json")
	pubBytes, err := os.ReadFile(pubPath)
	if err != nil {
		return nil, err
	}
	var pub map[string]any
	if err := json.Unmarshal(pubBytes, &pub); err != nil {
		return nil, err
	}
	report := map[string]any{
		"schema_version":       pub["schema_version"],
		"evidence_fingerprint": corpus.EvidenceFingerprint(events),
		"analysis_revision":    pub["analysis_revision"],
		"findings":             opaResult["findings"],
		"rejected_candidates":  opaResult["rejected_candidates"],
		"nodes":                opaResult["nodes"],
		"edges":                opaResult["edges"],
		"legacy_compatibility": opaResult["legacy_compatibility"],
	}
	return report, nil
}
