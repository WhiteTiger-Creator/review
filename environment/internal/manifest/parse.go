package manifest

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// Ext is the manifest file extension.
const Ext = ".slate"

// List returns the project names found in dir, ascending.
func List(dir string) ([]string, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, fmt.Errorf("manifests %s: %w", dir, err)
	}
	var names []string
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), Ext) {
			continue
		}
		names = append(names, strings.TrimSuffix(e.Name(), Ext))
	}
	sort.Strings(names)
	if len(names) == 0 {
		return nil, fmt.Errorf("manifests %s: no %s files", dir, Ext)
	}
	return names, nil
}

// Load parses <dir>/<project>.slate.
func Load(dir, project string) (*Manifest, error) {
	return ParseFile(filepath.Join(dir, project+Ext))
}

// ParseFile reads one manifest file.
func ParseFile(path string) (*Manifest, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("manifest %s: %w", path, err)
	}
	m := &Manifest{Requires: []Require{}, Overrides: []Override{}}
	stem := strings.TrimSuffix(filepath.Base(path), Ext)
	seenReq := map[string]bool{}
	seenOver := map[string]bool{}
	for n, line := range strings.Split(string(raw), "\n") {
		lineno := n + 1
		text := strings.TrimSpace(line)
		if text == "" || strings.HasPrefix(text, "#") {
			continue
		}
		fields := strings.Fields(text)
		switch fields[0] {
		case "project":
			if len(fields) != 2 {
				return nil, fmt.Errorf("manifest %s:%d: project takes one name", path, lineno)
			}
			if m.Project != "" {
				return nil, fmt.Errorf("manifest %s:%d: repeated project line", path, lineno)
			}
			m.Project = fields[1]
		case "require":
			req, err := parseRequire(fields[1:])
			if err != nil {
				return nil, fmt.Errorf("manifest %s:%d: %w", path, lineno, err)
			}
			if seenReq[req.Name] {
				return nil, fmt.Errorf("manifest %s:%d: %s required twice", path, lineno, req.Name)
			}
			seenReq[req.Name] = true
			m.Requires = append(m.Requires, req)
		case "override":
			if len(fields) != 3 {
				return nil, fmt.Errorf("manifest %s:%d: override takes a name and a version", path, lineno)
			}
			if seenOver[fields[1]] {
				return nil, fmt.Errorf("manifest %s:%d: %s overridden twice", path, lineno, fields[1])
			}
			seenOver[fields[1]] = true
			m.Overrides = append(m.Overrides, Override{Name: fields[1], Version: fields[2]})
		case "allow-yanked":
			if len(fields) != 2 || (fields[1] != "true" && fields[1] != "false") {
				return nil, fmt.Errorf("manifest %s:%d: allow-yanked takes true or false", path, lineno)
			}
			m.AllowYanked = fields[1] == "true"
		default:
			return nil, fmt.Errorf("manifest %s:%d: unknown directive %q", path, lineno, fields[0])
		}
	}
	if m.Project == "" {
		return nil, fmt.Errorf("manifest %s: missing project line", path)
	}
	if m.Project != stem {
		return nil, fmt.Errorf("manifest %s: project %q does not match file stem %q", path, m.Project, stem)
	}
	if len(m.Requires) == 0 {
		return nil, fmt.Errorf("manifest %s: no require lines", path)
	}
	return m, nil
}

func parseRequire(fields []string) (Require, error) {
	req := Require{Features: []string{}}
	if len(fields) < 2 {
		return req, fmt.Errorf("require takes a name and a range")
	}
	req.Name = fields[0]
	rest := fields[1:]
	if last := rest[len(rest)-1]; strings.HasPrefix(last, "+") {
		for _, f := range strings.Split(strings.TrimPrefix(last, "+"), ",") {
			if f == "" {
				return req, fmt.Errorf("empty feature name")
			}
			req.Features = append(req.Features, f)
		}
		sort.Strings(req.Features)
		rest = rest[:len(rest)-1]
	}
	if len(rest) == 0 {
		return req, fmt.Errorf("require takes a name and a range")
	}
	req.Range = strings.Join(rest, " ")
	return req, nil
}
