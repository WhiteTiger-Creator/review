package tags

import (
	"fmt"
	"strings"
)

type Set struct {
	enabled  map[string]bool
	disabled map[string]bool
}

func Parse(values []string) (Set, error) {
	set := Set{enabled: map[string]bool{}, disabled: map[string]bool{}}
	for _, raw := range values {
		if strings.TrimSpace(raw) == "" {
			return Set{}, fmt.Errorf("empty scenario tag")
		}
		if strings.HasPrefix(raw, "!") {
			name := strings.TrimPrefix(raw, "!")
			if name == "" {
				return Set{}, fmt.Errorf("empty negated scenario tag")
			}
			if set.enabled[name] {
				return Set{}, fmt.Errorf("conflicting scenario tags %q and %q", name, raw)
			}
			set.disabled[name] = true
			continue
		}
		if set.disabled[raw] {
			return Set{}, fmt.Errorf("conflicting scenario tags %q and !%s", raw, raw)
		}
		set.enabled[raw] = true
	}
	return set, nil
}

func (s Set) Matches(clauses [][]string) (bool, error) {
	if len(clauses) == 0 {
		clauses = [][]string{{}}
	}
	for _, clause := range clauses {
		matched := true
		for _, term := range clause {
			if strings.TrimSpace(term) == "" {
				return false, fmt.Errorf("empty package tag term")
			}
			if strings.HasPrefix(term, "!") {
				name := strings.TrimPrefix(term, "!")
				if !s.disabled[name] {
					matched = false
					break
				}
				continue
			}
			if !s.enabled[term] || s.disabled[term] {
				matched = false
				break
			}
		}
		if matched {
			return true, nil
		}
	}
	return false, nil
}
