package precedence

import (
	"os"
	"sort"
	"strings"

	"gopkg.in/yaml.v3"

	"migrator/internal/contracts"
	"migrator/internal/topology"
)

type Rule struct {
	Source      string
	Target      string
	Environment string
	Method      string
	Path        string
	Audiences   []string
	Deny        bool
}

type Legacy struct {
	GlobalAudiences []string
	EnvDefaults     map[string][]string
	ServiceDefaults map[string][]string
	EdgeRules       []Rule
}

func Load(path string, c *contracts.Contracts) (*Legacy, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var doc map[string]any
	if err := yaml.Unmarshal(raw, &doc); err != nil {
		return nil, err
	}
	l := &Legacy{EnvDefaults: map[string][]string{}, ServiceDefaults: map[string][]string{}}
	if g, ok := doc["global"].(map[string]any); ok {
		l.GlobalAudiences = normAud(g["audiences"], c)
	}
	if envs, ok := doc["environments"].(map[string]any); ok {
		for k, v := range envs {
			if m, ok := v.(map[string]any); ok {
				l.EnvDefaults[strings.ToLower(k)] = normAud(m["audiences"], c)
			}
		}
	}
	if svcs, ok := doc["services"].(map[string]any); ok {
		for k, v := range svcs {
			name := contracts.CanonicalService(k, c.Aliases)
			if m, ok := v.(map[string]any); ok {
				l.ServiceDefaults[name] = normAud(m["audiences"], c)
			}
		}
	}
	if edges, ok := doc["edges"].([]any); ok {
		for _, item := range edges {
			m, ok := item.(map[string]any)
			if !ok {
				continue
			}
			r := Rule{
				Source:      contracts.CanonicalService(str(m["source"]), c.Aliases),
				Target:      contracts.CanonicalService(str(m["target"]), c.Aliases),
				Environment: strings.ToLower(str(m["environment"])),
				Method:      strings.ToUpper(str(m["method"])),
				Path:        str(m["path"]),
				Audiences:   normAud(m["audiences"], c),
				Deny:        boolVal(m["deny"]),
			}
			l.EdgeRules = append(l.EdgeRules, r)
		}
	}
	sort.Slice(l.EdgeRules, func(i, j int) bool {
		a, b := l.EdgeRules[i], l.EdgeRules[j]
		return a.Source+a.Target+a.Environment+a.Method+a.Path < b.Source+b.Target+b.Environment+b.Method+b.Path
	})
	return l, nil
}

func (l *Legacy) Resolve(e topology.Edge) (audiences []string, deny bool) {
	if len(l.GlobalAudiences) > 0 {
		return l.GlobalAudiences, false
	}
	for _, r := range l.EdgeRules {
		if r.Source == e.Source && r.Target == e.Target && r.Environment == e.Environment && r.Method == e.Method && r.Path == e.Path {
			if r.Deny {
				return nil, true
			}
			if len(r.Audiences) > 0 {
				return r.Audiences, false
			}
		}
	}
	if a, ok := l.ServiceDefaults[e.Target]; ok && len(a) > 0 {
		return a, false
	}
	if a, ok := l.EnvDefaults[e.Environment]; ok && len(a) > 0 {
		return a, false
	}
	return l.GlobalAudiences, false
}

func str(v any) string {
	if v == nil {
		return ""
	}
	if s, ok := v.(string); ok {
		return s
	}
	return ""
}

func boolVal(v any) bool {
	if b, ok := v.(bool); ok {
		return b
	}
	return false
}

func normAud(v any, c *contracts.Contracts) []string {
	var raw []string
	switch t := v.(type) {
	case string:
		for _, p := range strings.Split(t, ",") {
			raw = append(raw, strings.TrimSpace(p))
		}
	case []any:
		for _, item := range t {
			raw = append(raw, strings.TrimSpace(str(item)))
		}
	case []string:
		raw = append(raw, t...)
	}
	out := make([]string, 0, len(raw))
	seen := map[string]struct{}{}
	for _, a := range raw {
		a = contracts.NormalizeAudience(a, c)
		if a == "" {
			continue
		}
		if _, ok := seen[a]; ok {
			continue
		}
		seen[a] = struct{}{}
		out = append(out, a)
	}
	sort.Strings(out)
	return out
}
