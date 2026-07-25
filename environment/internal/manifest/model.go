// Package manifest parses the project manifests under /app/manifests.
package manifest

// Require is one `require` line of a manifest.
type Require struct {
	Name     string   `json:"name"`
	Range    string   `json:"range"`
	Features []string `json:"features"`
}

// Override is one `override` line: a package pinned to an exact version.
type Override struct {
	Name    string `json:"name"`
	Version string `json:"version"`
}

// Manifest is a parsed project file.
type Manifest struct {
	Project     string     `json:"project"`
	Requires    []Require  `json:"requires"`
	Overrides   []Override `json:"overrides"`
	AllowYanked bool       `json:"allow_yanked"`
}

// Override returns the pinned version for a package and whether one exists.
func (m *Manifest) OverrideFor(name string) (string, bool) {
	for _, o := range m.Overrides {
		if o.Name == name {
			return o.Version, true
		}
	}
	return "", false
}
