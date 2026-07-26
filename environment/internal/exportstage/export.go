// Package exportstage writes the staging artifacts that sit between ingest and
// a published document.
package exportstage

import (
	"path/filepath"

	"slate/internal/canon"
	"slate/internal/manifest"
)

// ManifestDoc is the staging view of a parsed manifest.
type ManifestDoc struct {
	Protocol    string             `json:"protocol"`
	Project     string             `json:"project"`
	AllowYanked bool               `json:"allow_yanked"`
	Requires    []manifest.Require `json:"requires"`
	Overrides   []manifest.Override `json:"overrides"`
}

// Doc builds the staging view.
func Doc(m *manifest.Manifest) ManifestDoc {
	return ManifestDoc{
		Protocol:    canon.Protocol,
		Project:     m.Project,
		AllowYanked: m.AllowYanked,
		Requires:    m.Requires,
		Overrides:   m.Overrides,
	}
}

// Path is where the staging manifest lands under an output directory.
func Path(outDir, project string) string {
	return filepath.Join(outDir, "staging", project+".manifest.json")
}

// WriteManifest exports the staging manifest and returns its path.
func WriteManifest(outDir string, m *manifest.Manifest) (string, error) {
	path := Path(outDir, m.Project)
	if err := canon.Write(path, Doc(m)); err != nil {
		return "", err
	}
	return path, nil
}
