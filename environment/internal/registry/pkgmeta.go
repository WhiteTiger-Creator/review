// Package registry holds the on-disk registry model and the ingest stage that
// turns a registry directory into an in-memory index.
package registry

import "slate/internal/semver"

// Requirement is one edge declared by a release: a package name plus the
// range text exactly as written in the registry file.
type Requirement struct {
	Name  string `json:"name"`
	Range string `json:"range"`
}

// Release is one published version of a package.
type Release struct {
	Version  string                   `json:"version"`
	Yanked   bool                     `json:"yanked"`
	Requires []Requirement            `json:"requires"`
	Features map[string][]Requirement `json:"features"`
}

// Package is one registry file.
type Package struct {
	Name     string    `json:"name"`
	Releases []Release `json:"releases"`
}

// Semver parses the release version. Ingest has already validated it.
func (r Release) Semver() semver.Version { return semver.MustParse(r.Version) }

// FeatureNames lists the feature names of a release in ascending order.
func (r Release) FeatureNames() []string {
	names := make([]string, 0, len(r.Features))
	for name := range r.Features {
		names = append(names, name)
	}
	sortStrings(names)
	return names
}
